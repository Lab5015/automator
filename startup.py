import requests
requests.post("http://localhost:5558/register_tray",
            json={
                "label": "TRAY3",
                "RU0": True,
                "RU1": True,
                "RU2": True,
                "RU3": True,
                "RU4": True,
                "RU5": True,
            }
        )