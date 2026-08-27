from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.core.errors import error_info_from_exception

from .models import RequirementIntegrationBatch, TestCase, TestCaseEnhancementTask, TestCaseGenerationTask
from .integration import RequirementReviewService
from .services import RequirementImageAnalysisService, TestCaseGenerationError, TestCaseGenerationService
from .enhancement import TestCaseEnhancementService


@shared_task
def run_requirement_integration_batch(batch_id):
    batch = RequirementIntegrationBatch.objects.select_related("created_by").get(pk=batch_id)
    batch.status = "running"
    batch.started_at = timezone.now()
    batch.save(update_fields=["status", "started_at"])
    success_count = failed_count = 0
    errors = []
    error_infos = []
    for item in batch.requirement_items.select_related("project", "document").prefetch_related("content_blocks"):
        try:
            RequirementReviewService.integrate(item, batch.created_by, batch=batch)
            success_count += 1
        except Exception as exc:
            failed_count += 1
            info = error_info_from_exception(
                exc, details={"stage": "需求整合", "task_no": str(batch.id)},
            )
            error_infos.append(info)
            errors.append(f"{item.requirement_no}: {info['message']}")
    batch.success_count = success_count
    batch.failed_count = failed_count
    batch.status = "partial_success" if success_count and failed_count else ("completed" if success_count else "failed")
    batch.error_message = "\n".join(errors)[:5000]
    batch.error_info = error_infos[0] if error_infos else {}
    batch.completed_at = timezone.now()
    batch.save(update_fields=["success_count", "failed_count", "status", "error_message", "error_info", "completed_at"])


@shared_task
def run_testcase_generation_task(task_id):
    task = TestCaseGenerationTask.objects.select_related("project", "version", "created_by").get(pk=task_id)
    items = list(
        task.requirement_items
        .select_related("project", "document")
        .select_related("integration_draft")
        .prefetch_related("content_blocks__image_analysis")
        .order_by("module", "requirement_no", "id")
    )
    task.status = "running"
    task.progress = 0
    task.started_at = timezone.now()
    task.generation_log = []
    task.error_message = ""
    task.error_info = {}
    task.save(update_fields=["status", "progress", "started_at", "generation_log", "error_message", "error_info", "updated_at"])

    success_count = 0
    failed_count = 0
    logs = []
    task_errors = []

    for index, item in enumerate(items, start=1):
        log_entry = {
            "requirement_item": item.id,
            "requirement_no": item.requirement_no,
            "status": "running",
            "stage": "准备生成",
            "message": "开始处理详细需求",
        }
        logs.append(log_entry)
        task.generation_log = logs
        task.save(update_fields=["generation_log", "updated_at"])
        try:
            revision = task.requirement_revisions.filter(source_item=item).select_related("family").prefetch_related("modules").first()
            if not revision:
                raise TestCaseGenerationError("当前已发布版本中缺少该需求的正式修订")
            log_entry.update({"stage": "构建上下文", "message": "正在整理文本、表格和图片内容"})
            task.generation_log = logs
            task.save(update_fields=["generation_log", "updated_at"])
            image_blocks = [
                block for block in item.content_blocks.all()
                if block.block_type == "image" and (block.image_key or block.image_url)
            ]
            if image_blocks:
                log_entry.update({"stage": "识别图片", "message": f"正在识别 {len(image_blocks)} 张需求图片"})
                task.generation_log = logs
                task.save(update_fields=["generation_log", "updated_at"])
                RequirementImageAnalysisService.ensure_for_requirement(item)
            log_entry.update({"stage": "使用正式需求", "message": f"使用 {revision.family.family_no} R{revision.revision_no} 构建生成上下文"})
            requirement_context = (
                f"需求族: {revision.family.family_no}\n修订: R{revision.revision_no}\n"
                f"标题: {revision.title}\n模块: {'；'.join(module.path for module in revision.modules.all())}\n"
                f"需求描述:\n{revision.description}\n验收标准:\n{revision.acceptance_criteria or '无'}\n"
                f"补充描述:\n{revision.supplementary_description or '无'}\n来源摘要:\n{revision.source_summary or '无'}"
            )

            log_entry.update({"stage": "生成用例", "message": "正在调用测试用例生成专家"})
            task.generation_log = logs
            task.save(update_fields=["generation_log", "updated_at"])
            cases, _raw_content, writer_model, writer_role, generation_rounds = TestCaseGenerationService.generate_all_for_requirement(
                item, requirement_context=requirement_context
            )

            log_entry.update({
                "stage": "评审用例",
                "message": f"已通过 {generation_rounds} 轮生成 {len(cases)} 条用例，正在调用测试用例评审专家",
                "writer_role": writer_role.name,
                "writer_model": writer_model.model_name,
                "case_count": len(cases),
                "generation_rounds": generation_rounds,
            })
            task.generation_log = logs
            task.save(update_fields=["generation_log", "updated_at"])
            passed, feedback, reviewer_model, reviewer_role = TestCaseGenerationService.review_cases(
                item, cases, requirement_context=requirement_context
            )
            retried = False
            if not passed:
                retried = True
                log_entry.update({"stage": "重新生成", "message": "评审未通过，正在带审核意见重新生成"})
                task.generation_log = logs
                task.save(update_fields=["generation_log", "updated_at"])
                try:
                    retry_cases, _raw_content, retry_writer_model, retry_writer_role, retry_generation_rounds = TestCaseGenerationService.generate_all_for_requirement(
                        item, feedback, requirement_context=requirement_context
                    )
                except TestCaseGenerationError as exc:
                    feedback = f"{feedback}\n\n重新生成失败，已保留首轮可解析用例: {exc}"
                    log_entry.update({
                        "stage": "写入用例库",
                        "message": "重新生成返回不可解析内容，使用首轮已解析用例写入",
                        "retry_failed": True,
                    })
                else:
                    cases = retry_cases
                    writer_model = retry_writer_model
                    writer_role = retry_writer_role
                    log_entry.update({
                        "stage": "重新评审",
                        "message": f"已通过 {retry_generation_rounds} 轮重新生成 {len(cases)} 条用例，正在再次评审",
                        "writer_role": writer_role.name,
                        "writer_model": writer_model.model_name,
                        "case_count": len(cases),
                        "generation_rounds": retry_generation_rounds,
                    })
                    task.generation_log = logs
                    task.save(update_fields=["generation_log", "updated_at"])
                    passed, feedback, reviewer_model, reviewer_role = TestCaseGenerationService.review_cases(
                        item, cases, requirement_context=requirement_context
                    )

            log_entry.update({"stage": "写入用例库", "message": "评审完成，正在写入用例库"})
            task.generation_log = logs
            task.save(update_fields=["generation_log", "updated_at"])
            with transaction.atomic():
                for case in cases:
                    test_case, _ = TestCase.objects.update_or_create(
                        version=task.version,
                        requirement_item=item,
                        case_no=case["case_no"],
                        defaults={
                            "project": task.project,
                            "requirement_revision": revision,
                            "generation_task": task,
                            "title": case["title"],
                            "preconditions": case["preconditions"],
                            "steps": case["steps"],
                            "expected_result": case["expected_result"],
                            "priority": case["priority"],
                            "test_type": case["test_type"],
                            "status": "active",
                            "generated_by_model": writer_model.model_name,
                            "reviewed_by_model": reviewer_model.model_name,
                            "review_feedback": feedback,
                            "raw_content": case.get("raw") or case,
                            "created_by": task.created_by,
                        },
                    )
                    from apps.search.services import SearchIndexService
                    SearchIndexService.enqueue("test_case", test_case.id, task.project_id, revision.id, task.created_by)
            success_count += 1
            log_entry.update({
                "status": "success",
                "stage": "完成",
                "message": "详细需求用例生成完成",
                "case_count": len(cases),
                "review_passed": passed,
                "retried": retried,
                "writer_role": writer_role.name,
                "writer_model": writer_model.model_name,
                "reviewer_role": reviewer_role.name,
                "reviewer_model": reviewer_model.model_name,
            })
        except Exception as exc:
            failed_count += 1
            info = error_info_from_exception(
                exc,
                details={"stage": log_entry.get("stage") or "用例生成", "task_no": task.task_no},
            )
            task_errors.append(info)
            message = info["message"]
            log_entry.update({
                "status": "failed",
                "stage": "失败",
                "message": message,
                "error": info,
            })

        task.success_count = success_count
        task.failed_count = failed_count
        task.progress = int(index / max(len(items), 1) * 100)
        task.generation_log = logs
        task.save(update_fields=["success_count", "failed_count", "progress", "generation_log", "updated_at"])

    if success_count and failed_count:
        task.status = "partial_success"
        task.error_message = task_errors[0]["message"] if task_errors else "部分详细需求生成失败"
        task.error_info = task_errors[0] if task_errors else {}
    elif success_count:
        task.status = "completed"
    else:
        task.status = "failed"
        task.error_message = task_errors[0]["message"] if task_errors else "全部详细需求生成失败"
        task.error_info = task_errors[0] if task_errors else {}
    task.progress = 100
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "progress", "error_message", "error_info", "completed_at", "updated_at"])


@shared_task
def run_testcase_enhancement_task(task_id):
    task = (
        TestCaseEnhancementTask.objects.select_related("project", "version", "created_by")
        .get(pk=task_id)
    )
    revisions = list(
        task.requirement_revisions.select_related("family", "source_item")
        .prefetch_related("modules")
        .order_by("family__family_no", "revision_no", "id")
    )
    task.status = "running"
    task.progress = 0
    task.started_at = timezone.now()
    task.task_log = []
    task.error_message = ""
    task.error_info = {}
    task.save(update_fields=["status", "progress", "started_at", "task_log", "error_message", "error_info", "updated_at"])

    success_count = 0
    failed_count = 0
    logs = []
    snapshots = {}
    task_errors = []
    for index, revision in enumerate(revisions, start=1):
        entry = {
            "requirement_revision": revision.id,
            "requirement": f"{revision.family.family_no} R{revision.revision_no}",
            "title": revision.title,
            "status": "running",
            "stage": "检索历史资产",
        }
        logs.append(entry)
        task.task_log = logs
        task.save(update_fields=["task_log", "updated_at"])
        try:
            result = TestCaseEnhancementService.enhance_revision(task, revision)
            success_count += 1
            task.enhancer_model = result["enhancer_model"]
            task.reviewer_model = result["reviewer_model"]
            snapshots[str(revision.id)] = {
                "historical_case_count": result["historical_case_count"],
                "defect_count": result["defect_count"],
                "suggestion_count": result["suggestion_count"],
                "coverage_analysis": result["coverage_analysis"],
            }
            entry.update({
                "status": "success",
                "stage": "待人工确认",
                "message": f"生成 {result['suggestion_count']} 条增强建议",
                **snapshots[str(revision.id)],
            })
        except Exception as exc:
            failed_count += 1
            info = error_info_from_exception(
                exc,
                details={"stage": entry.get("stage") or "用例增强", "task_no": task.task_no},
            )
            task_errors.append(info)
            entry.update({"status": "failed", "stage": "失败", "message": info["message"], "error": info})
        task.success_count = success_count
        task.failed_count = failed_count
        task.progress = int(index / max(len(revisions), 1) * 100)
        task.task_log = logs
        task.retrieval_snapshot = snapshots
        task.save(update_fields=[
            "success_count", "failed_count", "progress", "task_log", "retrieval_snapshot",
            "enhancer_model", "reviewer_model", "updated_at",
        ])

    task.status = "partial_success" if success_count and failed_count else ("completed" if success_count else "failed")
    task.progress = 100
    task.error_message = task_errors[0]["message"] if task_errors else ""
    task.error_info = task_errors[0] if task_errors else {}
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "progress", "error_message", "error_info", "completed_at", "updated_at"])
