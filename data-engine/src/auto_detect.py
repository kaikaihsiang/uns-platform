import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("uns.auto_detect")

class AutoDetector:
    """
    Schema Auto-detector
    Collects payload samples for unknown topics and infers professional schema with JSONPaths.
    """
    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self.samples: Dict[str, List[Dict[str, Any]]] = {}

    def collect_sample(self, topic: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Collect a payload sample for a topic.
        Returns inferred schema if threshold is reached.
        """
        if topic not in self.samples:
            self.samples[topic] = []
        
        self.samples[topic].append(payload)
        logger.info(f"🔍 [AutoDetect] Collected sample {len(self.samples[topic])}/{self.threshold} for topic: {topic}")
        
        if len(self.samples[topic]) >= self.threshold:
            logger.info(f"✨ [AutoDetect] Threshold reached! Inferring professional schema for: {topic}")
            inferred = self.infer_schema(topic, self.samples[topic])
            # Clear samples after inference
            self.samples.pop(topic, None)
            return inferred
        
        return None

    def _flatten_json(self, data: Any, path: str = "$") -> List[Dict[str, Any]]:
        """
        Recursively flattens a JSON-like structure to generate JSONPath definitions.
        """
        fields = []
        if isinstance(data, dict):
            for key, val in data.items():
                current_path = f"{path}.{key}"
                if isinstance(val, dict) and val:
                    fields.extend(self._flatten_json(val, current_path))
                elif isinstance(val, list) and val:
                    if val and isinstance(val[0], dict):
                        fields.extend(self._flatten_json(val[0], f"{current_path}[0]"))
                    else:
                        fields.append({
                            "name": key,
                            "path": current_path,
                            "type": "array"
                        })
                else:
                    fields.append({
                        "name": key,
                        "path": current_path,
                        "type": self._get_type(val)
                    })
        return fields

    def infer_schema(self, topic: str, payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Infer schema from a list of payloads using recursive flattening.
        """
        field_map = {}
        
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            
            detected_fields = self._flatten_json(payload)
            for f in detected_fields:
                field_map[f["path"]] = f
        
        # Convert to list of fields suitable for UNS Schema
        fields = [
            {
                "name": f["name"],
                "path": f["path"],
                "type": f["type"],
                "extract": True,
                "persist": True
            } for f in field_map.values()
        ]
        
        return {
            "name": f"AutoDetect_{topic.replace('/', '_')}",
            "description": f"Inferred schema for {topic} (Generated at {datetime.now().isoformat()})",
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
            return "float"
        if isinstance(value, str):
            return "string"
        if isinstance(value, dict):
            return "json"
        if isinstance(value, list):
            return "array"
        return "string"
