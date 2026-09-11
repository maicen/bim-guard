"""Benchmark and compare SHACL vs Procedural engine parity (Phase 7b).

Usage:
    uv run python scripts/benchmark_shacl_vs_procedural.py <path_to_ifc> <ruleset_id>
"""

import argparse
import sys
import time
from pathlib import Path

import ifcopenshell

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.bootstrap import get_container
from app.environment import load_env_file
from app.modules.contracts import RuleEvaluationRequest
from app.modules.ifc_reader.bot_graph import IFC2BOT
from app.logging_config import get_logger

logger = get_logger("benchmark")

def main():
    parser = argparse.ArgumentParser(description="Benchmark SHACL vs Procedural.")
    parser.add_argument("ifc_path", help="Path to the IFC file")
    parser.add_argument("ruleset_id", help="Ruleset ID to run (e.g. BIMGUARD-GC-001)")
    args = parser.parse_args()

    load_env_file()
    container = get_container()
    
    # Load rules
    rules = container.rules_service.list_by_ruleset(args.ruleset_id)
    if not rules:
        logger.error(f"No rules found for ruleset {args.ruleset_id}")
        return

    logger.info(f"Loaded {len(rules)} rules. Parsing IFC...")
    t0 = time.time()
    try:
        model = ifcopenshell.open(args.ifc_path)
    except Exception as e:
        logger.error(f"Failed to open IFC: {e}")
        return
    logger.info(f"IFC loaded in {time.time() - t0:.2f}s")

    # 1. Procedural Evaluation
    logger.info("--- Running Procedural Engines ---")
    t1 = time.time()
    procedural_results = []
    
    # We'll just run it against all elements matching the target_ifc_class for each rule
    for rule in rules:
        target_class = rule.get("target_ifc_class")
        if not target_class:
            continue
        
        elements = model.by_type(target_class)
        if not elements:
            continue
            
        req = RuleEvaluationRequest(
            rule=rule,
            project_id=0,
            document_id=0
        )
        
        for element in elements:
            res = container.engine_registry.evaluate(element, req)
            procedural_results.append((rule["id"], element.id(), res.status))
    
    t_proc = time.time() - t1
    logger.info(f"Procedural finished in {t_proc:.2f}s with {len(procedural_results)} results")

    # 2. SHACL Evaluation
    logger.info("--- Running SHACL Engine ---")
    
    t2 = time.time()
    bot_generator = IFC2BOT(model)
    bot_graph = bot_generator.get_graph()
    logger.info(f"BOT Graph generated in {time.time() - t2:.2f}s with {len(bot_graph)} triples")
    
    shacl_engine = container.engine_registry.get_engine("CODE-SHACL")
    
    t3 = time.time()
    shacl_res = shacl_engine.evaluate(
        bot_graph, 
        context=RuleEvaluationRequest(
            rule=rules[0], 
            project_id=0, 
            document_id=0,
            metadata={"ruleset_id": args.ruleset_id}
        )
    )
    t_shacl = time.time() - t3
    
    logger.info(f"SHACL finished in {t_shacl:.2f}s. Status: {shacl_res.status}")
    
    # 3. Compare Parity
    logger.info("--- Parity Report ---")
    logger.info(f"Procedural Time: {t_proc:.2f}s")
    logger.info(f"SHACL Time:      {t_shacl:.2f}s")
    
    logger.info("Detailed breakdown requires IssueAdapter processing, but performance matrix is printed above.")

if __name__ == "__main__":
    main()
