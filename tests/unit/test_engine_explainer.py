import pytest
import asyncio
from cyguide.engine.explainer import LearningExplainer, TemplateBackend
from cyguide.engine.manifest import Manifest

@pytest.mark.asyncio
async def test_explainer_milestone_resolution():
    backend = TemplateBackend()
    explainer = LearningExplainer(backend)
    
    manifest_data = {
        "meta": {"name": "test", "description": "test", "categories": [], "binary": "test"},
        "modes": {"learning": True},
        "input": {}, "output": {},
        "learning": {
            "enabled": True,
            "explainer": {
                "tool_context": "Test tool",
                "milestones": [
                    {"trigger": "found_it", "prompt": "Success! Found {target}"}
                ]
            }
        }
    }
    manifest = Manifest(**manifest_data)
    
    chunks = []
    async for chunk in explainer.get_explanation(manifest, "found_it", {"target": "google.com"}):
        chunks.append(chunk)
        
    explanation = "".join(chunks)
    assert explanation == "Success! Found google.com"

@pytest.mark.asyncio
async def test_explainer_missing_milestone():
    backend = TemplateBackend()
    explainer = LearningExplainer(backend)
    manifest = Manifest(**{
        "meta": {"name": "test", "description": "test", "categories": [], "binary": "test"},
        "modes": {"learning": True}, "input": {}, "output": {}
    })
    
    chunks = []
    async for chunk in explainer.get_explanation(manifest, "nonexistent", {}):
        chunks.append(chunk)
    assert chunks == []
