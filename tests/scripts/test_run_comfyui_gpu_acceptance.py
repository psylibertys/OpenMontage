from scripts.run_comfyui_gpu_acceptance import _expand_cases


def test_expand_cases_skips_explicitly_disabled_cases():
    config = {
        "fixtures": {},
        "cases": [
            {
                "id": "keep",
                "tool": "comfyui_video",
                "workflow_template": "wan22_i2v_q6",
                "inputs": {},
            },
            {
                "id": "skip",
                "enabled": False,
                "tool": "comfyui_video",
                "workflow_template": "wan_scail_character",
                "inputs": {},
            },
        ],
    }

    assert [case["id"] for case in _expand_cases(config)] == ["keep"]
