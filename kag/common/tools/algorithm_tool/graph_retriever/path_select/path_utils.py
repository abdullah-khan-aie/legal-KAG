import concurrent.futures
import logging
import time

from kag.interface.solver.model.one_hop_graph import (
    EntityData,
)

logger = logging.getLogger()


def recall_one_hop_graph_by_entities(graph_api, heads: list[EntityData], tails: list[EntityData]):
    one_hop_graph_list = []
    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        map_dict = {"s": heads, "o": tails}
        for k, v in map_dict.items():
            if len(v) == 0:
                continue
            try:
                futures = [executor.submit(graph_api.get_entity_one_hop, entity) for entity in v]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
                for r in results:
                    if r is None:
                        continue
                    r.s_alias_name = k
                    one_hop_graph_list.append(r)
            except Exception as e:
                logger.debug(f"An error occurred in recall_one_hop_graph: {e}", exc_info=True)
    logger.info(f"recall_one_hop_graph cost {time.time() - start_time}")
    return one_hop_graph_list
