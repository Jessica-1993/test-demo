import hashlib
import json
import re

from django.db import transaction
from django.utils import timezone

from apps.configuration.models import PromptConfig
from apps.search.opensearch import OpenSearchGateway
from apps.search.services import SearchIndexService

from .models import (
    TestCase,
    TestCaseEnhancementEvidence,
    TestCaseEnhancementSuggestion,
)
from .services import LLMChatService, TestCaseGenerationError, TestCaseGenerationService


class TestCaseEnhancementError(RuntimeError):
    pass


class TestCaseEnhancementConflict(TestCaseEnhancementError):
    pass


class TestCaseEnhancementService:
    CASE_FIELDS = ("case_no", "title", "preconditions", "steps", "expected_result", "priority", "test_type")
    EVIDENCE_LIMIT = 12

    @classmethod
    def enhance_revision(cls, task, revision):
        current_cases = list(
            TestCase.objects.filter(
                project=task.project,
                version=task.version,
                requirement_item=revision.source_item,
                status="active",
            ).order_by("case_no", "id")
        )
        evidence = cls._retrieve_and_snapshot(task, revision, current_cases)
        enhancer_role = PromptConfig.resolve_active("testcase_enhancer", error_class=TestCaseEnhancementError)
        reviewer_role = PromptConfig.resolve_active("testcase_reviewer", error_class=TestCaseEnhancementError)
        prompt = cls._build_enhancement_prompt(task, revision, current_cases, evidence)
        content = LLMChatService(enhancer_role.llm_model).chat(enhancer_role.prompt_content, prompt)
        parsed = cls._parse_enhancement(content)
        suggestions = cls._normalize_suggestions(parsed.get("suggestions"), current_cases, evidence)
        reviews = cls._review_suggestions(reviewer_role, revision, current_cases, suggestions, evidence)
        created = cls._save_suggestions(task, revision, suggestions, reviews, evidence)
        return {
            "suggestion_count": len(created),
            "historical_case_count": sum(1 for item in evidence if item.asset_type == "test_case"),
            "defect_count": sum(1 for item in evidence if item.asset_type == "defect"),
            "enhancer_model": enhancer_role.llm_model.model_name,
            "reviewer_model": reviewer_role.llm_model.model_name,
            "coverage_analysis": str(parsed.get("coverage_analysis") or "")[:3000],
        }

    @classmethod
    def _retrieve_and_snapshot(cls, task, revision, current_cases):
        query = cls._query_text(revision, current_cases)
        module_ids = list(revision.modules.values_list("id", flat=True))
        gateway = OpenSearchGateway()
        selected = []
        seen = set()
        for asset_type, usage in (("test_case", "historical_case"), ("defect", "defect")):
            hits = gateway.hybrid_search(
                query,
                task.project_id,
                asset_type,
                version_sequence=task.version.sequence,
                module_ids=module_ids,
                size=40,
            )
            hits = cls._rank_hits(asset_type, hits, revision, task.version.sequence)
            type_count = 0
            for hit in hits:
                source = hit.get("_source", {})
                asset_id = source.get("asset_id")
                if not asset_id or (asset_type, asset_id) in seen:
                    continue
                seen.add((asset_type, asset_id))
                type_count += 1
                evidence = TestCaseEnhancementEvidence.objects.create(
                    task=task,
                    requirement_revision=revision,
                    usage=usage,
                    asset_type=asset_type,
                    asset_id=asset_id,
                    rank=type_count,
                    identifier=str(source.get("identifier") or "")[:120],
                    title=str(source.get("title") or "")[:300],
                    excerpt=str(source.get("text") or "")[:3000],
                    metadata={
                        "score": hit.get("_score"),
                        "version_sequence": source.get("version_sequence"),
                        "module_ids": source.get("module_ids") or [],
                        "authority": source.get("authority"),
                        "tags": source.get("tags") or [],
                    },
                )
                selected.append(evidence)
                if type_count >= cls.EVIDENCE_LIMIT:
                    break
        return selected

    @staticmethod
    def _rank_hits(asset_type, hits, revision, target_sequence):
        unique = {}
        for hit in hits:
            source = hit.get("_source", {})
            asset_id = source.get("asset_id")
            if not asset_id:
                continue
            if asset_type == "test_case" and int(source.get("version_sequence") or 0) >= target_sequence:
                continue
            current = unique.get(asset_id)
            if not current or float(hit.get("_score") or 0) > float(current.get("_score") or 0):
                unique[asset_id] = hit
        family_ids = {}
        severities = {}
        if asset_type == "test_case":
            family_ids = dict(
                TestCase.objects.filter(id__in=unique).values_list("id", "requirement_revision__family_id")
            )
        else:
            from apps.defects.models import Defect
            severities = dict(Defect.objects.filter(id__in=unique).values_list("id", "severity"))
        severity_weight = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        return sorted(
            unique.values(),
            key=lambda hit: (
                1 if family_ids.get(hit.get("_source", {}).get("asset_id")) == revision.family_id else 0,
                severity_weight.get(severities.get(hit.get("_source", {}).get("asset_id")), 0),
                float(hit.get("_score") or 0),
                str(hit.get("_source", {}).get("updated_at") or ""),
            ),
            reverse=True,
        )

    @classmethod
    def _query_text(cls, revision, current_cases):
        case_summaries = "\n".join(f"{case.case_no} {case.title} {case.expected_result}" for case in current_cases[:50])
        return "\n".join(filter(None, [
            revision.title,
            revision.description,
            revision.acceptance_criteria,
            revision.supplementary_description,
            case_summaries,
        ]))

    @classmethod
    def _build_enhancement_prompt(cls, task, revision, current_cases, evidence):
        current_payload = [{field: getattr(case, field) for field in cls.CASE_FIELDS} | {"id": case.id} for case in current_cases]
        evidence_payload = [
            {
                "ref": f"{item.asset_type}:{item.asset_id}",
                "type": item.asset_type,
                "identifier": item.identifier,
                "title": item.title,
                "excerpt": item.excerpt,
                "metadata": item.metadata,
            }
            for item in evidence
        ]
        requirement_payload = {
            "family_no": revision.family.family_no,
            "revision_no": revision.revision_no,
            "title": revision.title,
            "modules": [module.path for module in revision.modules.all()],
            "description": revision.description,
            "acceptance_criteria": revision.acceptance_criteria,
            "supplementary_description": revision.supplementary_description,
        }
        return (
            "请分析当前正式需求与当前用例，结合历史用例和缺陷证据提出增强建议。不得删除用例。\n"
            "只返回合法 JSON 对象，结构为: "
            '{"coverage_analysis":"...","suggestions":[{"action":"add|update","target_case_id":null,'
            '"proposed_content":{"case_no":"","title":"","preconditions":"","steps":"","expected_result":"",'
            '"priority":"high|medium|low","test_type":"functional|api|ui|integration|performance|security"},'
            '"rationale":"...","basis":"evidence|requirement","evidence_refs":["test_case:1","defect:2"]}]}。\n'
            "update 必须提供当前用例 ID；add 的 target_case_id 必须为 null。basis=evidence 时至少引用一条给定证据；"
            "basis=requirement 时 evidence_refs 可为空。不得引用未提供的证据。\n\n"
            f"目标版本: {task.version.version_no}\n"
            f"正式需求:\n{json.dumps(requirement_payload, ensure_ascii=False)}\n\n"
            f"当前版本用例:\n{json.dumps(current_payload, ensure_ascii=False)}\n\n"
            f"检索证据:\n{json.dumps(evidence_payload, ensure_ascii=False)}"
        )

    @classmethod
    def _parse_enhancement(cls, content):
        cleaned = TestCaseGenerationService._strip_code_fence(content or "")
        candidates = [cleaned]
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            candidates.append(match.group(0))
        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and isinstance(payload.get("suggestions", []), list):
                return payload
        raise TestCaseEnhancementError("增强模型未返回合法 JSON 对象")

    @classmethod
    def _normalize_suggestions(cls, raw_suggestions, current_cases, evidence):
        current_map = {case.id: case for case in current_cases}
        valid_refs = {f"{item.asset_type}:{item.asset_id}" for item in evidence}
        seen = set()
        normalized = []
        for raw in raw_suggestions or []:
            if not isinstance(raw, dict) or raw.get("action") not in {"add", "update"}:
                continue
            action = raw["action"]
            target_id = raw.get("target_case_id")
            if action == "update" and target_id not in current_map:
                continue
            content = raw.get("proposed_content")
            if not isinstance(content, dict):
                continue
            required = {"title", "steps", "expected_result"}
            if not all(str(content.get(field) or "").strip() for field in required):
                continue
            content = {field: str(content.get(field) or "") for field in cls.CASE_FIELDS}
            content["priority"] = content["priority"] if content["priority"] in {"high", "medium", "low"} else "medium"
            content["test_type"] = content["test_type"] if content["test_type"] in {"functional", "api", "ui", "integration", "performance", "security"} else "functional"
            basis = raw.get("basis") if raw.get("basis") in {"evidence", "requirement"} else "requirement"
            refs = [ref for ref in raw.get("evidence_refs", []) if ref in valid_refs]
            if basis == "evidence" and not refs:
                continue
            key = (action, target_id, content["title"], content["steps"], content["expected_result"])
            if key in seen:
                continue
            seen.add(key)
            normalized.append({
                "action": action,
                "target_case": current_map.get(target_id),
                "proposed_content": content,
                "rationale": str(raw.get("rationale") or "")[:5000],
                "basis": basis,
                "evidence_refs": refs,
            })
        return normalized

    @classmethod
    def _review_suggestions(cls, reviewer_role, revision, current_cases, suggestions, evidence):
        if not suggestions:
            return []
        prompt = (
            "请逐条评审用例增强建议是否符合当前正式需求、是否有证据支撑、是否与当前用例重复且可执行。\n"
            "只返回 JSON: {\"results\":[{\"index\":0,\"approved\":true,\"feedback\":\"...\"}]}。\n\n"
            f"正式需求:\n{revision.title}\n{revision.description}\n{revision.acceptance_criteria}\n\n"
            f"当前用例:\n{json.dumps([{field: getattr(case, field) for field in cls.CASE_FIELDS} | {'id': case.id} for case in current_cases], ensure_ascii=False)}\n\n"
            f"证据:\n{json.dumps([{'ref': f'{item.asset_type}:{item.asset_id}', 'title': item.title, 'excerpt': item.excerpt} for item in evidence], ensure_ascii=False)}\n\n"
            f"建议:\n{json.dumps(suggestions, ensure_ascii=False, default=lambda value: value.id if isinstance(value, TestCase) else str(value))}"
        )
        feedback = LLMChatService(reviewer_role.llm_model).chat(reviewer_role.prompt_content, prompt)
        cleaned = TestCaseGenerationService._strip_code_fence(feedback or "")
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", cleaned)
            payload = json.loads(match.group(0)) if match else {}
        reviews = {int(item.get("index")): item for item in payload.get("results", []) if isinstance(item, dict) and str(item.get("index", "")).isdigit()}
        fallback_passed = TestCaseGenerationService.review_passed(feedback)
        return [
            {
                "approved": bool(reviews.get(index, {}).get("approved", fallback_passed)),
                "feedback": str(reviews.get(index, {}).get("feedback") or feedback)[:5000],
            }
            for index in range(len(suggestions))
        ]

    @classmethod
    def _save_suggestions(cls, task, revision, suggestions, reviews, evidence):
        evidence_map = {f"{item.asset_type}:{item.asset_id}": item for item in evidence}
        created = []
        with transaction.atomic():
            for index, suggestion in enumerate(suggestions):
                target = suggestion["target_case"]
                before = cls.case_snapshot(target) if target else {}
                record = TestCaseEnhancementSuggestion.objects.create(
                    task=task,
                    requirement_revision=revision,
                    action=suggestion["action"],
                    target_case=target,
                    before_hash=cls.case_hash(target) if target else "",
                    before_snapshot=before,
                    proposed_content=suggestion["proposed_content"],
                    rationale=suggestion["rationale"],
                    evidence_basis=suggestion["basis"],
                    review_passed=reviews[index]["approved"],
                    review_feedback=reviews[index]["feedback"],
                )
                record.evidence.set([evidence_map[ref] for ref in suggestion["evidence_refs"]])
                created.append(record)
        return created

    @classmethod
    def accept(cls, suggestion, user, note=""):
        with transaction.atomic():
            suggestion = (
                TestCaseEnhancementSuggestion.objects.select_for_update()
                .select_related("task", "requirement_revision__source_item", "target_case")
                .get(pk=suggestion.pk)
            )
            if suggestion.status != "pending":
                raise TestCaseEnhancementError("仅待确认建议可以接受")
            if not suggestion.review_passed:
                raise TestCaseEnhancementError("模型评审未通过，不能直接接受")
            if suggestion.action == "update":
                case = TestCase.objects.select_for_update().get(pk=suggestion.target_case_id)
                if cls.case_hash(case) != suggestion.before_hash:
                    suggestion.status = "conflict"
                    suggestion.decision_note = "目标用例已发生变化，请重新增强或人工处理"
                    suggestion.decided_by = user
                    suggestion.decided_at = timezone.now()
                    suggestion.save(update_fields=["status", "decision_note", "decided_by", "decided_at", "updated_at"])
                    return suggestion
                cls._apply_content(case, suggestion.proposed_content, keep_case_no=True)
                case.review_feedback = suggestion.review_feedback
                case.reviewed_by_model = suggestion.task.reviewer_model
                raw = dict(case.raw_content or {})
                raw["enhancement"] = {"task": suggestion.task_id, "suggestion": suggestion.id, "before": suggestion.before_snapshot}
                case.raw_content = raw
                case.save()
            else:
                content = dict(suggestion.proposed_content)
                case_no = cls._available_case_no(suggestion, content.get("case_no"))
                case = TestCase(
                    project=suggestion.task.project,
                    version=suggestion.task.version,
                    requirement_item=suggestion.requirement_revision.source_item,
                    requirement_revision=suggestion.requirement_revision,
                    case_no=case_no,
                    status="active",
                    generated_by_model=suggestion.task.enhancer_model,
                    reviewed_by_model=suggestion.task.reviewer_model,
                    review_feedback=suggestion.review_feedback,
                    raw_content={"enhancement": {"task": suggestion.task_id, "suggestion": suggestion.id}},
                    created_by=user,
                )
                cls._apply_content(case, content, keep_case_no=True)
                case.case_no = case_no
                case.save()
            suggestion.status = "accepted"
            suggestion.applied_case = case
            suggestion.decision_note = note
            suggestion.decided_by = user
            suggestion.decided_at = timezone.now()
            suggestion.save(update_fields=["status", "applied_case", "decision_note", "decided_by", "decided_at", "updated_at"])
            SearchIndexService.enqueue("test_case", case.id, case.project_id, suggestion.requirement_revision_id, user)
            return suggestion

    @staticmethod
    def reject(suggestion, user, note=""):
        if suggestion.status not in {"pending", "conflict"}:
            raise TestCaseEnhancementError("当前建议不能拒绝")
        suggestion.status = "rejected"
        suggestion.decision_note = note
        suggestion.decided_by = user
        suggestion.decided_at = timezone.now()
        suggestion.save(update_fields=["status", "decision_note", "decided_by", "decided_at", "updated_at"])
        return suggestion

    @classmethod
    def case_snapshot(cls, case):
        return {field: getattr(case, field) for field in cls.CASE_FIELDS}

    @classmethod
    def case_hash(cls, case):
        payload = json.dumps(cls.case_snapshot(case), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def _apply_content(cls, case, content, keep_case_no=False):
        for field in cls.CASE_FIELDS:
            if field == "case_no" and keep_case_no:
                continue
            value = content.get(field)
            if value not in (None, "") or field in {"preconditions"}:
                setattr(case, field, value)

    @staticmethod
    def _available_case_no(suggestion, proposed):
        proposed = str(proposed or "").strip()[:80]
        queryset = TestCase.objects.filter(version=suggestion.task.version, requirement_item=suggestion.requirement_revision.source_item)
        if proposed and not queryset.filter(case_no=proposed).exists():
            return proposed
        return f"TC-E{suggestion.task_id}-{suggestion.id}"
