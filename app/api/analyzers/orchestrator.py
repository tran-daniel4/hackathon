import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from analyzers.base import Analyzer
from analyzers.file_index import FileIndex
from analyzers.detectors.repo_detector import RepoDetector
from analyzers.detectors.service_detector import ServiceDetector
from analyzers.extractors.route_extractor import RouteExtractor
from analyzers.extractors.http_client_extractor import HttpClientExtractor
from analyzers.extractors.datastore_extractor import DatastoreExtractor
from analyzers.extractors.cache_extractor import CacheExtractor
from analyzers.extractors.messaging_extractor import MessagingExtractor
from analyzers.extractors.external_integration_extractor import ExternalIntegrationExtractor
from graph.graph_builder import GraphBuilder
from graph.models import GraphFacts

logger = logging.getLogger(__name__)


class AnalyzerOrchestrator:
    def __init__(self) -> None:
        self.analyzers: list[Analyzer] = [
            RepoDetector(),
            ServiceDetector(),
            RouteExtractor(),
            HttpClientExtractor(),
            DatastoreExtractor(),
            CacheExtractor(),
            MessagingExtractor(),
            ExternalIntegrationExtractor(),
        ]

    def run(
        self,
        file_index: FileIndex,
        analysis_id: Optional[str] = None,
        repo_meta: Optional[dict] = None,
    ) -> GraphFacts:
        if analysis_id is None:
            analysis_id = str(uuid.uuid4())

        if repo_meta is None:
            repo_meta = {
                "name": "uploaded",
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }

        patches = []
        for analyzer in self.analyzers:
            try:
                if analyzer.supports(file_index):
                    patch = analyzer.analyze(file_index)
                    patches.append(patch)
                    logger.debug(
                        "%s: %d nodes, %d edges, %d apis, %d evidence",
                        analyzer.name(),
                        len(patch.nodes),
                        len(patch.edges),
                        len(patch.apis),
                        len(patch.evidence),
                    )
            except Exception as exc:
                logger.warning("Analyzer %s failed: %s", analyzer.name(), exc, exc_info=True)

        return GraphBuilder().build(patches, analysis_id, repo_meta=repo_meta)
