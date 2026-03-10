import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger("uns.auto_detect")

class AutoDetector:
    """
    Schema Auto-detector
    Collects payload samples for unknown topics and infers schema.
    """
    def __init__(self, threshold: int = 10):
        self.threshold = threshold
        self.samples: Dict[str, List[Dict[str, Any]]] = {}
        # threshold is threshold for triggering inference

    def collect_sample(self, topic: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Collect a payload sample for a topic.
        Returns inferred schema if threshold is reached.
        """
        if topic not in self.samples:
            self.samples[topic] = []
        
        self.samples[topic].append(payload)
        
        if len(self.samples[topic]) >= self.threshold:
            logger.info(f"Threshold reached for topic {topic}. Inferring schema...")
            inferred = self.infer_schema(topic, self.samples[topic])
            # Clear samples after inference
            self.samples.pop(topic, None)
            return inferred
        
        return None

    def infer_schema(self, topic: str, payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Infer schema from a list of payloads.
        Returns field definitions as a list of {"name": str, "type": str}.
        """
        field_map = {}
        
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            for key, value in payload.items():
                if key not in field_map:
                    field_map[key] = self._get_type(value)
        
        # Convert to list of objects
        fields = [{"name": k, "type": t} for k, t in field_map.items()]
        
        return {
            "name": f"AutoDetect_{topic.replace('/', '_')}",
            "description": f"Inferred schema for {topic}",
            "definition": fields,
            "topic_pattern": topic,
            "is_suggested": True
        }

    def _get_type(self, value: Any) -> str:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, dict):
            return "object"
        if isinstance(value, list):
            return "array"
        return "string"
