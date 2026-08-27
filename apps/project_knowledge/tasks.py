import json
import re

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.core.errors import error_info_from_exception

from apps.configuration.models import PromptConfig
from apps.requirements.models import RequirementDocument, RequirementRevision
from apps.requirements.services import LLMChatService, TestCaseGenerationError, TestCaseGenerationService

from .models import KnowledgeExtractionRun, ProjectKnowledgeEvidence, ProjectKnowledgeItem, ProjectKnowledgeRevision


@shared_task
def run_knowledge_extraction(run_id):
    run = KnowledgeExtractionRun.objects.select_related("project", "created_by").get(pk=run_id)
    run.status = "running"
    run.error_message = ""
    run.error_info = {}
    run.save(update_fields=["status", "error_message", "error_info"])
    try:
        role = PromptConfig.resolve_active("requirement_integrator", error_class=TestCaseGenerationError)
        source_parts = []
        documents = RequirementDocument.objects.filter(project=run.project, id__in=run.source_document_ids)
        for document in documents:
            source_parts.append(f"[document:{document.id}] {document.title}\n{document.extracted_text}")
        if run.include_confirmed_requirements:
            revisions = RequirementRevision.objects.filter(family__project=run.project).select_related("family", "module")
            for revision in revisions:
                source_parts.append(f"[requirement_revision:{revision.id}] {revision.family.family_no} {revision.title}\n{revision.description}\n{revision.acceptance_criteria}")
        if run.project.description:
            source_parts.insert(0, f"[project:{run.project_id}] {run.project.name}\n{run.project.description}")
        if not source_parts:
            raise TestCaseGenerationError("没有可用于提取项目知识的来源")
        prompt = (
            "请从以下可信材料中提取原子化项目知识候选。输出合法JSON数组，不要Markdown。"
            "每项字段: category,title,content,tags,source_type,source_id,source_locator,excerpt。"
            "category只能是term,role_permission,module_boundary,business_rule,business_flow,non_functional,external_dependency。"
            "不得推测材料没有明确表达的规则。\n\n" + "\n\n".join(source_parts)
        )
        content = LLMChatService(role.llm_model).chat(role.prompt_content, prompt)
        candidates = _parse_candidates(content)
        with transaction.atomic():
            for candidate in candidates:
                base_code = re.sub(r"[^a-z0-9]+", "-", candidate["title"].lower()).strip("-") or f"knowledge-{run.id}"
                code = base_code[:68]
                suffix = 1
                while ProjectKnowledgeItem.objects.filter(project=run.project, code=code).exists():
                    suffix += 1
                    code = f"{base_code[:60]}-{suffix}"
                item = ProjectKnowledgeItem.objects.create(
                    project=run.project,
                    code=code,
                    category=candidate["category"],
                    title=candidate["title"][:200],
                    tags=candidate.get("tags") or [],
                )
                conflict = ProjectKnowledgeRevision.objects.filter(
                    item__project=run.project,
                    item__category=item.category,
                    item__title=item.title,
                    status="confirmed",
                ).exclude(content=candidate["content"]).exists()
                revision = ProjectKnowledgeRevision.objects.create(
                    item=item,
                    revision_no=1,
                    title=item.title,
                    content=candidate["content"],
                    status="conflict" if conflict else "candidate",
                    model_name=role.llm_model.model_name,
                    created_by=run.created_by,
                )
                ProjectKnowledgeEvidence.objects.create(
                    revision=revision,
                    source_type=candidate.get("source_type") or "unknown",
                    source_id=int(candidate.get("source_id") or run.project_id),
                    source_locator=candidate.get("source_locator") or "",
                    excerpt=candidate.get("excerpt") or candidate["content"],
                )
        run.status = "completed"
        run.candidate_count = len(candidates)
        run.model_name = role.llm_model.model_name
    except Exception as exc:
        info = error_info_from_exception(
            exc, details={"stage": "项目知识提取", "task_no": str(run.id)},
        )
        run.status = "failed"
        run.error_message = info["message"]
        run.error_info = info
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "candidate_count", "model_name", "error_message", "error_info", "completed_at"])


def _parse_candidates(content):
    cleaned = TestCaseGenerationService._strip_code_fence(content or "")
    match = re.search(r"\[[\s\S]*\]", cleaned)
    data = json.loads(match.group(0) if match else cleaned)
    if not isinstance(data, list):
        raise TestCaseGenerationError("项目知识提取结果必须是JSON数组")
    allowed = {choice[0] for choice in ProjectKnowledgeItem.CATEGORY_CHOICES}
    result = []
    for item in data:
        if not isinstance(item, dict) or item.get("category") not in allowed or not item.get("title") or not item.get("content"):
            continue
        result.append(item)
    if not result:
        raise TestCaseGenerationError("项目知识提取结果没有有效候选")
    return result
