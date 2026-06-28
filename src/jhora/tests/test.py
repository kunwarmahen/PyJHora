#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import copy
import json
import os

from jhora import config as old_config
from jhora import const


OUTPUT_FILE = os.path.join(const._DATA_DIR, "factory_settings.json")


def export_factory_settings(output_file: str = OUTPUT_FILE) -> None:
    """
    Export the active runtime metadata from the current working config.py
    into a flattened factory_settings.json.
    """
    # Load from existing config backend
    old_config.load_all_settings(create_if_missing=False, apply=False)
    setting_defs = old_config.get_all_setting_defs()

    factory = {}

    for key, meta in setting_defs.items():
        item = {
            "label": meta.get("label", key),
            "type": meta.get("type", "string"),
            "default": copy.deepcopy(meta.get("default")),
            "tab": meta.get("tab", "User"),
            "section": meta.get("section", "general"),
            "order": int(meta.get("order", 0)),
            "visible": bool(meta.get("visible", True))
        }

        # Optional metadata
        if meta.get("description"):
            item["description"] = meta["description"]
        if meta.get("nullable", False):
            item["nullable"] = True
        if meta.get("read_only", False):
            item["read_only"] = True
        if "min" in meta:
            item["min"] = meta["min"]
        if "max" in meta:
            item["max"] = meta["max"]

        # Resolve explicit or provider-based choices into real values
        try:
            choices = old_config._resolve_choices(meta)
        except Exception:
            choices = []

        if choices:
            item["choices"] = copy.deepcopy(choices)

        # Flatten binding
        binding = meta.get("binding", {})
        setter = binding.get("setter")
        target = binding.get("target")

        # Preserve minimal binding info in a simplified form
        if setter:
            item["setter"] = setter
        elif target:
            item["const_name"] = target

        # Keep adapter / enum_class only if still needed later
        if binding.get("adapter"):
            item["adapter"] = binding["adapter"]
        if binding.get("enum_class"):
            item["enum_class"] = binding["enum_class"]
        if binding.get("exclude"):
            item["exclude"] = copy.deepcopy(binding["exclude"])

        factory[key] = item

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(factory, f, ensure_ascii=False, indent=2)

    print(f"Exported {len(factory)} settings to:")
    print(output_file)


if __name__ == "__main__":
    export_factory_settings()