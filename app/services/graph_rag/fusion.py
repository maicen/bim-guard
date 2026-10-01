"""Reciprocal Rank Fusion (RRF) and candidate rank aggregation for Graph-RAG."""

from typing import Any


def compute_reciprocal_rank_fusion(
    streams: dict[str, list[dict[str, Any]]],
    k: int = 60,
    top_n: int = 6,
    id_key: str = "id",
) -> list[dict[str, Any]]:
    """Compute Reciprocal Rank Fusion (RRF) scores across multiple ranked streams.

    Formula: RRF_score(d) = sum_{m in streams} 1 / (k + rank_m(d))

    Args:
        streams: Mapping of stream name (e.g. 'vector', 'bm25', 'graph') to ordered candidate list.
        k: Smoothing constant penalizing lower ranks (default: 60, standard SOTA value).
        top_n: Maximum candidates to return after score aggregation.
        id_key: Preferred key to identify candidate items (default: 'id').

    Returns:
        Ordered list of candidate dicts with added 'rrf_score', 'stream_ranks', and 'rrf_stream_ranks'.
    """
    scores: dict[str, float] = {}
    item_map: dict[str, dict[str, Any]] = {}
    stream_ranks: dict[str, dict[str, int]] = {}

    for stream_name, candidates in streams.items():
        for rank, candidate in enumerate(candidates, start=1):
            cid = str(
                candidate.get(id_key)
                or candidate.get("id")
                or candidate.get("guid")
                or f"cand_{rank}"
            )
            if cid not in item_map:
                item_map[cid] = candidate
                stream_ranks[cid] = {}

            stream_ranks[cid][stream_name] = rank
            rrf_increment = 1.0 / (k + rank)
            scores[cid] = scores.get(cid, 0.0) + rrf_increment

    # Sort candidates by combined RRF score descending
    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    results: list[dict[str, Any]] = []
    for cid in sorted_ids[:top_n]:
        item = dict(item_map[cid])
        item["rrf_score"] = round(scores[cid], 6)
        item["stream_ranks"] = stream_ranks[cid]
        item["rrf_stream_ranks"] = stream_ranks[cid]
        results.append(item)

    return results
