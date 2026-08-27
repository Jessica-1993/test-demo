import hashlib
import json
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.core.errors import error_info_from_exception

from apps.project_knowledge.models import ProjectModule
from apps.search.opensearch import OpenSearchGateway
from apps.search.services import SearchIndexService

from .models import (
    RequirementConflict,
    RequirementFamily,
    RequirementIntegrationDraft,
    RequirementIntegrationEvidence,
    RequirementIntegrationRun,
    RequirementMatchCandidate,
    RequirementOpenQuestion,
    RequirementRevision,
)
from .services import RequirementContextBuilder, RequirementIntegrationService, TestCaseGenerationService


class RequirementReviewError(RuntimeError):
    pass


class RequirementReviewService:
    SEARCH_TYPES = ("project_knowledge_revision", "requirement_revision", "test_case")

    @staticmethod
    def source_hash(item):
        value = "\n".join([
            item.title or "", item.module or "", item.description or "",
            item.acceptance_criteria or "", item.supplementary_description or "",
        ])
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _optional_positive_id(value):
        if value in (None, "") or isinstance(value, bool):
            return None
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return None
        return normalized if normalized > 0 else None

    @classmethod
    def integrate(cls, item, user, batch=None):
        source_hash = cls.source_hash(item)
        run = RequirementIntegrationRun.objects.create(
            batch=batch, requirement_item=item,
            status="running", source_content_hash=source_hash, created_by=user,
        )
        try:
            query = RequirementContextBuilder.build(item)
            sibling_context = cls._current_document_context(item)
            hits = cls._search(query, item.project_id)
            role = RequirementIntegrationService.get_active_role()
            module_catalog = cls._module_catalog(item.project_id)
            prompt = cls._build_prompt(item, query, sibling_context, hits, module_catalog)
            from .services import LLMChatService
            content = LLMChatService(role.llm_model).chat(role.prompt_content, prompt)
            data = cls._parse(content)
            with transaction.atomic():
                cls._save_results(run, item, user, source_hash, query, sibling_context, hits, data, role)
        except Exception as exc:
            info = error_info_from_exception(
                exc, details={"stage": "需求整合", "task_no": str(run.id)},
            )
            run.status = "failed"
            run.error_message = info["message"]
            run.error_info = info
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "error_message", "error_info", "completed_at"])
            raise
        return run

    @classmethod
    def _search(cls, query, project_id):
        gateway = OpenSearchGateway()
        hits = []
        for asset_type in cls.SEARCH_TYPES:
            for hit in gateway.hybrid_search(query, project_id, asset_type, size=20):
                source = hit.get("_source", {})
                source["_score"] = hit.get("_score")
                source["_id"] = hit.get("_id")
                hits.append(source)
        return hits

    @staticmethod
    def _current_document_context(item):
        siblings = (
            item.document.items
            .filter(is_current=True, is_archived=False)
            .exclude(pk=item.pk)
            .order_by("module", "requirement_no", "id")
        )
        return [
            {
                "id": sibling.id,
                "requirement_no": sibling.requirement_no,
                "module": sibling.module,
                "title": sibling.title,
                "description": sibling.description,
                "acceptance_criteria": sibling.acceptance_criteria,
                "supplementary_description": sibling.supplementary_description,
            }
            for sibling in siblings
        ]

    @staticmethod
    def _build_prompt(item, raw_context, sibling_context, hits, module_catalog):
        evidence = [
            {
                "asset_type": hit.get("asset_type"), "asset_id": hit.get("asset_id"),
                "revision_id": hit.get("revision_id"), "identifier": hit.get("identifier"),
                "title": hit.get("title"), "text": hit.get("text", "")[:1800],
                "authority": hit.get("authority"),
            }
            for hit in hits[:40]
        ]
        return (
            "请结合项目知识、历史正式需求、测试覆盖提示，以及当前文档中的其他候选需求，整合当前候选需求。\n"
            "当前文档其他候选需求用于识别重复、互补、依赖和冲突，但不能覆盖当前需求原文中的有效事实。\n"
            "只返回 JSON 对象，必须包含 title,module_paths,description,acceptance_criteria,"
            "supplementary_description,source_summary,relationship_mode,change_type,selected_revision_id,"
            "conflicts,open_questions,evidence_refs。\n"
            "relationship_mode 只能是 new/existing；change_type 只能是 initial/continued/modified/deprecated。\n"
            "conflicts 为 [{title,current_statement,historical_statement}]；open_questions 为 [{category,question}]；"
            "evidence_refs 为 [{asset_type,asset_id,revision_id,usage}]。\n\n"
            "module_paths 必须是字符串数组，只能从正式模块目录的 path 中选择完整路径；可选择多个父节点或叶子节点。\n"
            f"当前项目正式模块目录:\n{json.dumps(module_catalog, ensure_ascii=False)}\n\n"
            f"当前需求 ID: {item.id}\n当前原文:\n{raw_context}\n\n"
            f"当前文档其他候选需求:\n{json.dumps(sibling_context, ensure_ascii=False)}\n\n"
            f"检索证据:\n{json.dumps(evidence, ensure_ascii=False)}"
        )

    @staticmethod
    def _parse(content):
        cleaned = TestCaseGenerationService._strip_code_fence(content or "")
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if not match:
                raise RequirementReviewError("需求整合模型未返回合法 JSON")
            data = json.loads(match.group(0))
        if not isinstance(data, dict):
            raise RequirementReviewError("需求整合结果必须是 JSON 对象")
        if data.get("relationship_mode") not in {"new", "existing"}:
            raise RequirementReviewError("模型未给出有效的需求关系")
        if not isinstance(data.get("module_paths"), list):
            raise RequirementReviewError("模型未返回 module_paths 数组")
        return data

    @staticmethod
    def _module_catalog(project_id):
        modules = list(
            ProjectModule.objects.filter(project_id=project_id, status="active")
            .select_related("parent__parent__parent")
            .prefetch_related("aliases")
            .order_by("sort_order", "id")
        )
        return [
            {
                "id": module.id,
                "code": module.code,
                "path": module.path,
                "aliases": [alias.alias for alias in module.aliases.all()],
                "description": module.description,
            }
            for module in modules
        ]

    @classmethod
    def _save_results(cls, run, item, user, source_hash, raw_context, sibling_context, hits, data, role):
        run.model_name = role.llm_model.model_name
        run.prompt_name = role.name
        run.search_snapshot = {
            "hit_count": len(hits),
            "current_document_requirement_count": len(sibling_context),
            "asset_counts": {
                kind: sum(1 for hit in hits if hit.get("asset_type") == kind)
                for kind in cls.SEARCH_TYPES
            },
        }
        run.status = "completed"
        run.completed_at = timezone.now()
        run.save()

        for rank, hit in enumerate(hits, start=1):
            asset_id = cls._optional_positive_id(hit.get("asset_id"))
            revision_id = cls._optional_positive_id(hit.get("revision_id"))
            if not asset_id:
                continue
            RequirementIntegrationEvidence.objects.create(
                run=run, usage="coverage" if hit.get("asset_type") == "test_case" else "fact",
                asset_type=hit.get("asset_type", ""), asset_id=asset_id,
                asset_revision_id=revision_id, chunk_id=hit.get("_id", ""),
                source_locator=hit.get("source_locator", ""), excerpt=hit.get("text", "")[:3000],
            )
            if hit.get("asset_type") == "requirement_revision" and revision_id:
                revision = RequirementRevision.objects.filter(pk=revision_id).first()
                if revision:
                    RequirementMatchCandidate.objects.get_or_create(
                        run=run, revision=revision,
                        defaults={"rrf_rank": rank, "matched_excerpt": hit.get("text", "")[:1500]},
                    )

        selected_revision_id = cls._optional_positive_id(data.get("selected_revision_id"))
        selected_revision = (
            RequirementRevision.objects.filter(pk=selected_revision_id, family__project=item.project)
            .select_related("family")
            .prefetch_related("modules")
            .first()
            if selected_revision_id
            else None
        )
        relationship_mode = data.get("relationship_mode")
        if relationship_mode == "existing" and not selected_revision:
            raise RequirementReviewError("模型判定为历史需求，但未给出有效历史修订")
        suggested_paths, matched_modules, unresolved_paths = cls._resolve_modules(item, data.get("module_paths"))
        draft, _ = RequirementIntegrationDraft.objects.get_or_create(requirement_item=item, defaults={"created_by": user})
        draft.suggested_module_paths = suggested_paths
        draft.unresolved_module_paths = unresolved_paths
        draft.module_resolution_status = "resolved" if matched_modules and not unresolved_paths else "needs_review"
        draft.selected_family = selected_revision.family if selected_revision else None
        draft.relationship_mode = relationship_mode
        draft.change_type = data.get("change_type") or ("initial" if relationship_mode == "new" else "modified")
        draft.relationship_confirmed = False
        draft.review_status = "pending"
        draft.source_content_hash = source_hash
        draft.status = "completed"
        draft.raw_context = raw_context
        draft.model_name = role.llm_model.model_name
        draft.prompt_name = role.name
        draft.updated_by = user
        for field in RequirementIntegrationService.EDITABLE_FIELDS:
            setattr(draft, field, str(data.get(field) or getattr(item, field, "") or ""))
        draft.save()
        draft.formal_modules.set(matched_modules)

        for conflict in data.get("conflicts") or []:
            RequirementConflict.objects.create(
                run=run, title=str(conflict.get("title") or "规则冲突")[:200],
                current_statement=str(conflict.get("current_statement") or ""),
                historical_statement=str(conflict.get("historical_statement") or ""),
            )
        for question in data.get("open_questions") or []:
            RequirementOpenQuestion.objects.create(
                run=run, category=str(question.get("category") or "")[:40], question=str(question.get("question") or ""),
            )

    @staticmethod
    def _normalize_path(value):
        return "/".join(part.strip().casefold() for part in str(value or "").split("/") if part.strip())

    @classmethod
    def _resolve_modules(cls, item, suggested_paths):
        unique_paths = []
        seen = set()
        for path in suggested_paths or []:
            display_path = " / ".join(part.strip() for part in str(path).split("/") if part.strip())
            normalized = cls._normalize_path(display_path)
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_paths.append(display_path)
        active_modules = list(ProjectModule.objects.filter(project=item.project, status="active").select_related("parent"))
        by_path = {cls._normalize_path(module.path): module for module in active_modules}
        matched = [by_path[cls._normalize_path(path)] for path in unique_paths if cls._normalize_path(path) in by_path]
        unresolved = [path for path in unique_paths if cls._normalize_path(path) not in by_path]
        return unique_paths, matched, unresolved

    @classmethod
    def confirm(cls, item, user):
        existing_revision = RequirementRevision.objects.filter(source_item=item).first()
        if existing_revision:
            return existing_revision
        try:
            draft = item.integration_draft
        except RequirementIntegrationDraft.DoesNotExist as exc:
            raise RequirementReviewError("请先完成需求整合") from exc
        run = item.integration_runs.filter(status="completed").first()
        if not run or draft.status != "completed" or draft.review_status != "approved":
            raise RequirementReviewError("需求整合稿尚未审核通过")
        if draft.source_content_hash != cls.source_hash(item):
            raise RequirementReviewError("需求原文已变更，请重新整合并审核")
        if not draft.relationship_confirmed:
            raise RequirementReviewError("请先人工确认需求关系")
        if run.conflicts.filter(status="pending").exists():
            raise RequirementReviewError("存在未处理的需求冲突")
        modules = list(draft.formal_modules.all())
        if not modules:
            raise RequirementReviewError("请先选择正式模块")
        if draft.unresolved_module_paths or draft.module_resolution_status != "resolved":
            raise RequirementReviewError("存在未解决的模块路径，请先人工处理")
        invalid_modules = [module.id for module in modules if module.project_id != item.project_id or module.status != "active"]
        if invalid_modules:
            raise RequirementReviewError(f"正式模块已停用或不属于当前项目: {invalid_modules}")
        with transaction.atomic():
            if draft.relationship_mode == "new":
                family_no = cls._next_family_no(item.project_id)
                family = RequirementFamily.objects.create(
                    project=item.project, family_no=family_no,
                    title=draft.title, created_by=user,
                )
                previous = None
            else:
                family = draft.selected_family
                if not family:
                    raise RequirementReviewError("请选择历史需求族")
                previous = family.revisions.order_by("-revision_no").first()
            revision_no = (family.revisions.aggregate(value=Max("revision_no"))["value"] or 0) + 1
            revision = RequirementRevision.objects.create(
                family=family, source_item=item, previous_revision=previous, revision_no=revision_no,
                change_type=draft.change_type or ("initial" if previous is None else "modified"),
                title=draft.title, description=draft.description,
                acceptance_criteria=draft.acceptance_criteria,
                supplementary_description=draft.supplementary_description,
                source_summary=draft.source_summary, source_content_hash=draft.source_content_hash,
                confirmed_by=user,
            )
            revision.modules.set(modules)
            family.modules.set(modules)
            item.formal_modules.set(modules)
            item.confirm_status = "confirmed"
            item.confirmed_by = user
            item.confirmed_at = timezone.now()
            item.save(update_fields=["confirm_status", "confirmed_by", "confirmed_at", "updated_at"])
            SearchIndexService.enqueue("requirement_revision", revision.id, item.project_id, revision.id, user, content_hash=draft.source_content_hash)
        return revision

    @staticmethod
    def _next_family_no(project_id):
        prefix = f"REQ-F-{project_id}-"
        latest = RequirementFamily.objects.filter(project_id=project_id, family_no__startswith=prefix).order_by("-id").first()
        number = int(latest.family_no.rsplit("-", 1)[-1]) + 1 if latest else 1
        return f"{prefix}{number:04d}"
