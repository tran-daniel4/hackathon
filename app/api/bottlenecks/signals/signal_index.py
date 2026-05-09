from __future__ import annotations

from analyzers.file_index import FileIndex
from bottlenecks.evidence import EvidenceRegistry
from bottlenecks.models import RepoSignals
from bottlenecks.signals.cache_signal_extractor import extract_cache_calls
from bottlenecks.signals.code_signal_extractor import extract_cpu_calls, extract_loops
from bottlenecks.signals.db_signal_extractor import extract_db_calls
from bottlenecks.signals.dependency_signal_extractor import extract_dependency_signals
from bottlenecks.signals.file_io_signal_extractor import extract_file_io_calls
from bottlenecks.signals.http_signal_extractor import extract_http_calls
from bottlenecks.signals.logging_signal_extractor import extract_logging_calls
from bottlenecks.signals.queue_signal_extractor import extract_queue_configs
from bottlenecks.signals.route_signal_extractor import extract_route_signals
from graph.models import GraphFacts


def build_repo_signals(file_index: FileIndex, facts: GraphFacts) -> RepoSignals:
    evidence = EvidenceRegistry(facts)
    routes = extract_route_signals(file_index, facts)
    loops = extract_loops(file_index, facts.analysis_id, routes, evidence)
    http_calls = extract_http_calls(file_index, routes, evidence)
    db_calls = extract_db_calls(file_index, routes, loops, evidence)
    cache_calls = extract_cache_calls(file_index, routes, evidence)
    queue_configs = extract_queue_configs(file_index, facts, evidence)
    file_io_calls = extract_file_io_calls(file_index, routes, evidence)
    logging_calls = extract_logging_calls(file_index, routes, loops, evidence)
    dependency_signals = extract_dependency_signals(file_index, evidence)
    cpu_calls = extract_cpu_calls(file_index, routes, evidence)

    return RepoSignals(
        analysis_id=facts.analysis_id,
        routes=routes,
        http_calls=http_calls,
        db_calls=db_calls,
        loops=loops,
        cache_calls=cache_calls,
        queue_configs=queue_configs,
        file_io_calls=file_io_calls,
        logging_calls=logging_calls,
        dependency_signals=dependency_signals,
        cpu_calls=cpu_calls,
    )
