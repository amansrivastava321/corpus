"""DashboardService — aggregates data from all Corpus subsystems."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

_log = logging.getLogger(__name__)


class DashboardService:
    """Read-only aggregator. Never mutates any state."""

    def __init__(self, container) -> None:
        self._c = container

    async def get_summary(self) -> dict:
        health = await self._c.runtime_service.get_health()

        # Products
        products = await self._c.product_service.list_all()
        presence_map = {}
        try:
            for p in products:
                pid = p.get("product_id") if isinstance(p, dict) else p.product_id
                pname = p.get("name") if isinstance(p, dict) else p.name
                state = self._c.presence_tracker.get_state(pid)
                presence_map[pname] = state
        except Exception:
            pass

        # Signals
        signals_data = await self._safe(self._c.delivery_service.get_delivery_stats, {})

        # Checkpoints
        checkpoints = await self._safe(
            lambda: self._c.checkpoint_service.list_all(status="WAITING_CLEARANCE"),
            [],
        )
        blocked = await self._safe(
            lambda: self._c.checkpoint_service.list_all(status="BLOCKED"),
            [],
        )

        # Memory
        episodes = await self._safe(
            lambda: self._c.memory_service.list_episodes(limit=10),
            [],
        )

        # Orchestrations
        workflows = await self._safe(
            lambda: self._c.workflow_engine.list_workflows(limit=10),
            [],
        )

        # Guardian
        guardian_status = await self._safe(
            self._c.guardian_engine.get_status,
            {},
        )

        # Guardian interventions
        interventions = await self._safe(
            lambda: self._c.guardian_engine._state.list_interventions(limit=5),
            [],
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "system": health,
            "products": {
                "total": len(products),
                "online": sum(1 for s in presence_map.values() if s == "ONLINE"),
                "presence": presence_map,
            },
            "signals": signals_data,
            "checkpoints": {
                "waiting_clearance": len(checkpoints),
                "blocked": len(blocked),
            },
            "memory": {
                "recent_episodes": len(episodes),
            },
            "orchestration": {
                "recent_workflows": len(workflows),
            },
            "guardian": guardian_status,
            "policy": {
                "mode": self._c.policy_engine.mode.value,
            },
        }

    async def get_products(self) -> dict:
        products = await self._c.product_service.list_all()
        result = []
        for p in products:
            pid = p.get("product_id") if isinstance(p, dict) else p.product_id
            pname = p.get("name") if isinstance(p, dict) else p.name
            try:
                presence = self._c.presence_tracker.get_state(pid)
            except Exception:
                presence = "UNKNOWN"
            item = p if isinstance(p, dict) else p.model_dump()
            item["presence"] = presence
            result.append(item)
        return {"products": result, "count": len(result)}

    async def get_signals(self) -> dict:
        return await self._safe(self._c.delivery_service.get_delivery_stats, {})

    async def get_checkpoints(self) -> dict:
        all_cp = await self._safe(
            self._c.checkpoint_service.list_all,
            [],
        )
        by_status: dict[str, int] = {}
        for cp in all_cp:
            s = cp.get("status", "UNKNOWN") if isinstance(cp, dict) else cp.status
            by_status[s] = by_status.get(s, 0) + 1
        return {"checkpoints": all_cp[:20], "by_status": by_status, "total": len(all_cp)}

    async def get_orchestrations(self) -> dict:
        workflows = await self._safe(
            lambda: self._c.workflow_engine.list_workflows(limit=20),
            [],
        )
        return {
            "workflows": [w.to_dict() for w in workflows],
            "count": len(workflows),
        }

    async def get_guardian(self) -> dict:
        status = await self._safe(self._c.guardian_engine.get_status, {})
        interventions = await self._safe(
            lambda: self._c.guardian_engine._state.list_interventions(limit=20),
            [],
        )
        return {
            "status": status,
            "interventions": [i.to_dict() for i in interventions],
            "count": len(interventions),
        }

    async def get_memory(self) -> dict:
        episodes = await self._safe(
            lambda: self._c.memory_service.list_episodes(limit=20),
            [],
        )
        patterns = await self._safe(
            lambda: self._c.memory_service._store.list_patterns(),
            [],
        )
        return {
            "episodes": episodes,
            "patterns": patterns,
            "episode_count": len(episodes),
            "pattern_count": len(patterns),
        }

    async def get_audit(self) -> dict:
        return {
            "note": "Audit trail is queryable via GET /checkpoints/{id}/history",
            "audit_table": "checkpoint_events",
        }

    async def get_timeline(self, limit: int = 50) -> dict:
        """Returns recent events across all subsystems ordered by time."""
        events: list[dict] = []

        episodes = await self._safe(lambda: self._c.memory_service.list_episodes(limit=limit), [])
        for ep in episodes:
            events.append({
                "timestamp": ep.get("created_at", ""),
                "source": "memory",
                "type": ep.get("signal_type", ""),
                "summary": f"{ep.get('source_product')} → {ep.get('target_product')} [{ep.get('outcome', '?')}]",
            })

        interventions = await self._safe(
            lambda: self._c.guardian_engine._state.list_interventions(limit=20), []
        )
        for iv in interventions:
            events.append({
                "timestamp": iv.created_at,
                "source": "guardian",
                "type": iv.action.value,
                "summary": f"Guardian: {iv.action.value} — {iv.reason[:60]}",
            })

        events.sort(key=lambda e: e["timestamp"], reverse=True)
        return {"timeline": events[:limit], "count": len(events)}

    @staticmethod
    async def _safe(coro_or_fn, default):
        try:
            if callable(coro_or_fn):
                result = coro_or_fn()
                if hasattr(result, "__await__"):
                    return await result
                return result
        except Exception:
            pass
        return default
