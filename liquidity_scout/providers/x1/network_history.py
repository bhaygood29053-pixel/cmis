"""Official X1 cluster-history provider primitives for CMIS.

This module owns read-only collection from the public ``api.x1.xyz`` cluster
history endpoint. It preserves provider values as returned, validates dataset
alignment deterministically, and does not perform CMIS-level interpretation or
risk calculations.
"""

from typing import Any, Dict, Iterable, List

import requests


CHAIN = "x1"
DEFAULT_NETWORK = "mainnet"
CLUSTER_HISTORY_URL = "https://api.x1.xyz/v1/cluster/history"
NETWORK_HISTORY_SOURCE = "api.x1.xyz /v1/cluster/history"
DEFAULT_GROUP_BY = "epoch"
DEFAULT_ORDER = "asc"
DEFAULT_PROPERTIES = (
    "currentValidators",
    "activatedStake",
    "totalSupply",
)


class X1NetworkHistoryAPIError(RuntimeError):
    """Raised when X1 cluster-history data cannot be verified."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_properties(properties: Iterable[str]) -> List[str]:
    result = []
    for value in properties:
        item = _text(value)
        if not item:
            raise ValueError("X1 network-history properties cannot contain blanks.")
        result.append(item)
    if not result:
        raise ValueError("At least one X1 network-history property is required.")
    return result


def parse_cluster_history(payload: Any) -> Dict[str, Any]:
    """Validate the chart-style history payload without reinterpreting values."""
    if not isinstance(payload, dict):
        raise X1NetworkHistoryAPIError("X1 cluster history must be a JSON object.")

    labels = payload.get("labels")
    datasets = payload.get("datasets")
    if not isinstance(labels, list) or not isinstance(datasets, list):
        raise X1NetworkHistoryAPIError(
            "X1 cluster history requires labels and datasets arrays."
        )

    label_count = len(labels)
    parsed_datasets = []
    seen_names = set()
    for dataset in datasets:
        if not isinstance(dataset, dict):
            raise X1NetworkHistoryAPIError("X1 cluster history dataset is malformed.")
        name = _text(dataset.get("name"))
        label = _text(dataset.get("label"))
        data = dataset.get("data")
        if not name or not label or not isinstance(data, list):
            raise X1NetworkHistoryAPIError(
                "X1 cluster history dataset requires name, label, and data."
            )
        if name in seen_names:
            raise X1NetworkHistoryAPIError(
                f"X1 cluster history contains duplicate dataset {name!r}."
            )
        if len(data) != label_count:
            raise X1NetworkHistoryAPIError(
                f"X1 cluster history dataset {name!r} does not align with labels."
            )
        seen_names.add(name)
        parsed_datasets.append({"name": name, "label": label, "data": list(data)})

    return {"labels": list(labels), "datasets": parsed_datasets}


def fetch_cluster_history(
    *,
    network: str = DEFAULT_NETWORK,
    group_by: str = DEFAULT_GROUP_BY,
    chart_format: bool = False,
    order: str = DEFAULT_ORDER,
    properties: Iterable[str] = DEFAULT_PROPERTIES,
    url: str = CLUSTER_HISTORY_URL,
    timeout: int = 15,
    get=requests.get,
) -> Dict[str, Any]:
    """Fetch and validate official X1 cluster history."""
    network = _text(network).lower()
    group_by = _text(group_by)
    order = _text(order).lower()
    url = _text(url)
    properties = _normalize_properties(properties)

    if not network:
        raise ValueError("X1 network is required.")
    if not group_by:
        raise ValueError("X1 history group_by is required.")
    if order not in {"asc", "desc"}:
        raise ValueError("X1 history order must be 'asc' or 'desc'.")
    if not url:
        raise ValueError("X1 cluster-history URL is required.")

    params = {
        "network": network,
        "groupBy": group_by,
        "chartFormat": "true" if chart_format else "false",
        "order": order,
        "filterProperties": ",".join(properties),
    }

    try:
        response = get(
            url,
            params=params,
            headers={"accept": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        parsed = parse_cluster_history(response.json())
    except X1NetworkHistoryAPIError:
        raise
    except Exception as exc:
        raise X1NetworkHistoryAPIError(
            f"X1 cluster-history request failed: {exc}"
        ) from exc

    return {
        "chain": CHAIN,
        "network": network,
        "group_by": group_by,
        "chart_format": bool(chart_format),
        "order": order,
        "properties": properties,
        "labels": parsed["labels"],
        "datasets": parsed["datasets"],
        "source": NETWORK_HISTORY_SOURCE,
        "observed_at": None,
    }


class X1NetworkHistoryProvider:
    """Explicit provider facade for official X1 cluster-history facts."""

    chain = CHAIN
    source = NETWORK_HISTORY_SOURCE

    def __init__(
        self,
        *,
        network: str = DEFAULT_NETWORK,
        url: str = CLUSTER_HISTORY_URL,
        timeout: int = 15,
        get=requests.get,
    ):
        self.network = _text(network).lower()
        self.url = _text(url)
        self.timeout = timeout
        self.get = get
        if not self.network:
            raise ValueError("X1 network is required.")
        if not self.url:
            raise ValueError("X1 cluster-history URL is required.")

    def get_history(
        self,
        *,
        group_by: str = DEFAULT_GROUP_BY,
        chart_format: bool = False,
        order: str = DEFAULT_ORDER,
        properties: Iterable[str] = DEFAULT_PROPERTIES,
    ) -> Dict[str, Any]:
        return fetch_cluster_history(
            network=self.network,
            group_by=group_by,
            chart_format=chart_format,
            order=order,
            properties=properties,
            url=self.url,
            timeout=self.timeout,
            get=self.get,
        )


__all__ = [
    "CHAIN",
    "CLUSTER_HISTORY_URL",
    "DEFAULT_GROUP_BY",
    "DEFAULT_NETWORK",
    "DEFAULT_ORDER",
    "DEFAULT_PROPERTIES",
    "NETWORK_HISTORY_SOURCE",
    "X1NetworkHistoryAPIError",
    "X1NetworkHistoryProvider",
    "fetch_cluster_history",
    "parse_cluster_history",
]
