import json
import math
import re
from urllib.parse import quote

from django.conf import settings

from apps.configuration.models import PromptConfig
from apps.requirements.services import LLMChatService, normalize_gemini_base_url, normalize_gemini_model_name

from .services import SearchUnavailableError


INDEX_VERSION = "testhub-assets-v2-multi-module-768"
SEARCH_PIPELINE = "testhub-assets-rrf"


class EmbeddingService:
    @staticmethod
    def active_config():
        return PromptConfig.resolve_active("embedding", error_class=SearchUnavailableError).llm_model

    @classmethod
    def embed(cls, text, task_type):
        config = cls.active_config()
        if config.protocol != "gemini":
            raise SearchUnavailableError("首期文本向量模型必须使用 Gemini 协议")
        if config.embedding_dimension != 768:
            raise SearchUnavailableError("当前OpenSearch索引固定为768维，请使用768维embedding配置")
        base_url = normalize_gemini_base_url(config.base_url)
        model = quote(normalize_gemini_model_name(config.model_name), safe="/")
        url = f"{base_url}/{model}:embedContent?key={quote(config.api_key, safe='')}"
        payload = {
            "model": f"models/{normalize_gemini_model_name(config.model_name).split('/')[-1]}",
            "content": {"parts": [{"text": text}]},
            "taskType": task_type,
            "outputDimensionality": config.embedding_dimension,
        }
        data = LLMChatService._post_json(
            url, payload, {"Content-Type": "application/json"},
            provider=config.provider, stage="文本向量化",
        )
        try:
            vector = data["embedding"]["values"]
        except (KeyError, TypeError) as exc:
            raise SearchUnavailableError("向量模型响应缺少 embedding.values") from exc
        if len(vector) != config.embedding_dimension:
            raise SearchUnavailableError(f"向量维度错误，期望{config.embedding_dimension}，实际{len(vector)}")
        norm = math.sqrt(sum(float(value) ** 2 for value in vector)) or 1.0
        return [float(value) / norm for value in vector]


class OpenSearchGateway:
    def __init__(self):
        try:
            from opensearchpy import OpenSearch
        except ImportError as exc:
            raise SearchUnavailableError("缺少 opensearch-py 依赖") from exc
        kwargs = {
            "hosts": [settings.OPENSEARCH_URL],
            "timeout": settings.OPENSEARCH_TIMEOUT,
            "use_ssl": settings.OPENSEARCH_URL.startswith("https://"),
            "verify_certs": settings.OPENSEARCH_URL.startswith("https://"),
        }
        if settings.OPENSEARCH_USERNAME:
            kwargs["http_auth"] = (settings.OPENSEARCH_USERNAME, settings.OPENSEARCH_PASSWORD)
        self.client = OpenSearch(**kwargs)

    def health(self):
        return self.client.cluster.health()

    def ensure_index(self):
        self.client.transport.perform_request(
            "PUT",
            f"/_search/pipeline/{SEARCH_PIPELINE}",
            body={
                "description": "TestHub BM25 + vector RRF",
                "phase_results_processors": [
                    {"score-ranker-processor": {"combination": {"technique": "rrf", "rank_constant": 60}}}
                ],
            },
        )
        if not self.client.indices.exists(index=INDEX_VERSION):
            self.client.indices.create(
                index=INDEX_VERSION,
                body={
                    "settings": {
                        "index.knn": True,
                        "index.search.default_pipeline": SEARCH_PIPELINE,
                        "analysis": {"analyzer": {"testhub_icu": {"type": "icu_analyzer"}}},
                    },
                    "mappings": {
                        "dynamic": "strict",
                        "properties": {
                            "document_kind": {"type": "keyword"},
                            "asset_type": {"type": "keyword"},
                            "asset_id": {"type": "long"},
                            "revision_id": {"type": "long"},
                            "project_id": {"type": "long"},
                            "module_ids": {"type": "long"},
                            "version_sequence": {"type": "integer"},
                            "status": {"type": "keyword"},
                            "authority": {"type": "keyword"},
                            "identifier": {"type": "keyword"},
                            "title": {"type": "text", "analyzer": "testhub_icu", "fields": {"raw": {"type": "keyword"}}},
                            "text": {"type": "text", "analyzer": "testhub_icu"},
                            "tags": {"type": "keyword"},
                            "chunk_type": {"type": "keyword"},
                            "chunk_no": {"type": "integer"},
                            "source_locator": {"type": "keyword"},
                            "content_hash": {"type": "keyword"},
                            "updated_at": {"type": "date"},
                            "embedding": {
                                "type": "knn_vector",
                                "dimension": 768,
                                "method": {"name": "hnsw", "engine": "lucene", "space_type": "cosinesimil"},
                            },
                        },
                    },
                },
            )
        alias_exists = self.client.indices.exists_alias(name=settings.OPENSEARCH_INDEX_ALIAS)
        aliases = self.client.indices.get_alias(name=settings.OPENSEARCH_INDEX_ALIAS) if alias_exists else {}
        if INDEX_VERSION not in aliases:
            actions = []
            actions.extend({"remove": {"index": name, "alias": settings.OPENSEARCH_INDEX_ALIAS}} for name in aliases)
            actions.append({"add": {"index": INDEX_VERSION, "alias": settings.OPENSEARCH_INDEX_ALIAS}})
            self.client.indices.update_aliases(body={"actions": actions})

    def upsert_asset(self, asset_type, asset_id):
        self.ensure_index()
        docs = AssetDocumentBuilder.build(asset_type, asset_id)
        self.client.delete_by_query(
            index=settings.OPENSEARCH_INDEX_ALIAS,
            body={"query": {"bool": {"filter": [{"term": {"asset_type": asset_type}}, {"term": {"asset_id": asset_id}}]}}},
            conflicts="proceed",
            refresh=True,
        )
        for doc_id, payload in docs:
            self.client.index(index=settings.OPENSEARCH_INDEX_ALIAS, id=doc_id, body=payload, refresh=False)
        self.client.indices.refresh(index=settings.OPENSEARCH_INDEX_ALIAS)
        return len(docs)

    def delete_asset(self, asset_type, asset_id):
        self.ensure_index()
        return self.client.delete_by_query(
            index=settings.OPENSEARCH_INDEX_ALIAS,
            body={"query": {"bool": {"filter": [{"term": {"asset_type": asset_type}}, {"term": {"asset_id": asset_id}}]}}},
            conflicts="proceed",
            refresh=True,
        )

    def hybrid_search(self, text, project_id, asset_type, version_sequence=None, module_ids=None, size=50):
        self.ensure_index()
        vector = EmbeddingService.embed(text, "RETRIEVAL_QUERY")
        filters = [
            {"term": {"project_id": project_id}},
            {"term": {"asset_type": asset_type}},
            {"term": {"document_kind": "chunk"}},
            {"term": {"status": "confirmed"}},
        ]
        if version_sequence is not None:
            filters.append({"range": {"version_sequence": {"lte": version_sequence}}})
        if module_ids:
            filters.append({"terms": {"module_ids": self._expand_module_ids(module_ids)}})
        body = {
            "size": size,
            "_source": {"excludes": ["embedding"]},
            "query": {
                "hybrid": {
                    "filter": {"bool": {"filter": filters}},
                    "queries": [
                        {"multi_match": {"query": text, "fields": ["identifier^8", "title^4", "tags^3", "text"]}},
                        {"knn": {"embedding": {"vector": vector, "k": size}}},
                    ],
                }
            },
        }
        result = self.client.search(index=settings.OPENSEARCH_INDEX_ALIAS, body=body)
        return result.get("hits", {}).get("hits", [])

    @staticmethod
    def _expand_module_ids(module_ids):
        from apps.project_knowledge.models import ProjectModule

        scope = {int(module_id) for module_id in module_ids}
        frontier = list(scope)
        while frontier:
            children = list(ProjectModule.objects.filter(parent_id__in=frontier).values_list("id", flat=True))
            frontier = [module_id for module_id in children if module_id not in scope]
            scope.update(frontier)
        return sorted(scope)


class AssetDocumentBuilder:
    @classmethod
    def build(cls, asset_type, asset_id):
        if asset_type == "project_knowledge_revision":
            return cls._knowledge(asset_id)
        if asset_type == "requirement_revision":
            return cls._requirement(asset_id)
        if asset_type == "test_case":
            return cls._test_case(asset_id)
        if asset_type == "defect":
            return cls._defect(asset_id)
        raise ValueError(f"不支持的索引资产类型: {asset_type}")

    @classmethod
    def _knowledge(cls, asset_id):
        from apps.project_knowledge.models import ProjectKnowledgeRevision

        revision = ProjectKnowledgeRevision.objects.select_related("item__project", "item__module", "effective_from_version").get(pk=asset_id)
        if revision.status != "confirmed":
            return []
        return cls._documents(
            "project_knowledge_revision", revision.id, revision.id, revision.item.project_id,
            [revision.item.module_id] if revision.item.module_id else [], revision.effective_from_version.sequence if revision.effective_from_version else 0,
            revision.item.code, revision.title, revision.content, revision.item.tags, "authoritative", revision.created_at,
        )

    @classmethod
    def _requirement(cls, asset_id):
        from apps.requirements.models import RequirementRevision

        revision = RequirementRevision.objects.select_related("family__project").prefetch_related("versions", "modules").get(pk=asset_id)
        sequences = list(revision.versions.values_list("sequence", flat=True))
        text = "\n\n".join(filter(None, [revision.description, revision.acceptance_criteria, revision.supplementary_description, revision.source_summary]))
        return cls._documents(
            "requirement_revision", revision.id, revision.id, revision.family.project_id, list(revision.modules.values_list("id", flat=True)),
            min(sequences) if sequences else 0, revision.family.family_no, revision.title, text, [], "primary", revision.confirmed_at,
        )

    @classmethod
    def _test_case(cls, asset_id):
        from apps.requirements.models import TestCase

        case = TestCase.objects.select_related("project", "version", "requirement_revision").prefetch_related("requirement_revision__modules").get(pk=asset_id)
        if case.status != "active" or not case.requirement_revision_id:
            return []
        text = "\n\n".join(filter(None, [case.preconditions, case.steps, case.expected_result]))
        return cls._documents(
            "test_case", case.id, case.requirement_revision_id, case.project_id, list(case.requirement_revision.modules.values_list("id", flat=True)),
            case.version.sequence, case.case_no, case.title, text, [case.test_type, case.priority], "supporting", case.updated_at,
        )

    @classmethod
    def _defect(cls, asset_id):
        from apps.defects.models import Defect

        defect = Defect.objects.select_related("project", "detected_version").prefetch_related("modules").get(pk=asset_id)
        if defect.knowledge_status != "confirmed":
            return []
        text = "\n\n".join(filter(None, [
            defect.description,
            defect.reproduction_steps,
            defect.actual_result,
            defect.expected_result,
            defect.root_cause,
            defect.resolution,
        ]))
        tags = list(defect.tags or []) + [defect.severity, defect.lifecycle_status]
        return cls._documents(
            "defect", defect.id, None, defect.project_id,
            list(defect.modules.values_list("id", flat=True)),
            defect.detected_version.sequence if defect.detected_version else 0,
            defect.defect_no, defect.title, text, tags, "supporting", defect.updated_at,
        )

    @classmethod
    def _documents(cls, asset_type, asset_id, revision_id, project_id, module_ids, version_sequence, identifier, title, text, tags, authority, updated_at):
        chunks = cls._split(text)
        documents = []
        base = {
            "asset_type": asset_type,
            "asset_id": asset_id,
            "revision_id": revision_id,
            "project_id": project_id,
            "module_ids": module_ids or [],
            "version_sequence": version_sequence,
            "status": "confirmed",
            "authority": authority,
            "identifier": identifier,
            "title": title,
            "tags": tags or [],
            "source_locator": "",
            "content_hash": cls._hash(f"{title}\n{text}"),
            "updated_at": updated_at.isoformat(),
        }
        main_text = f"{title}\n{text[:3000]}".strip()
        main = {**base, "document_kind": "asset", "text": main_text, "chunk_type": "summary", "chunk_no": 0, "embedding": EmbeddingService.embed(main_text, "RETRIEVAL_DOCUMENT")}
        documents.append((f"{asset_type}:{asset_id}:asset", main))
        for index, chunk in enumerate(chunks, start=1):
            payload = {**base, "document_kind": "chunk", "text": chunk, "chunk_type": "content", "chunk_no": index, "embedding": EmbeddingService.embed(chunk, "RETRIEVAL_DOCUMENT")}
            documents.append((f"{asset_type}:{asset_id}:chunk:{index}", payload))
        return documents

    @staticmethod
    def _split(text, limit=3000, overlap=400):
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text or "") if part.strip()]
        if not paragraphs:
            return ["无正文"]
        chunks = []
        current = ""
        for paragraph in paragraphs:
            if len(current) + len(paragraph) + 2 <= limit:
                current = f"{current}\n\n{paragraph}".strip()
                continue
            if current:
                chunks.append(current)
            while len(paragraph) > limit:
                chunks.append(paragraph[:limit])
                paragraph = paragraph[limit - overlap:]
            current = paragraph
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _hash(value):
        import hashlib
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
