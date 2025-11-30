#EVENTBUS AND OBSERVER

import threading

class EventBus:
    def __init__(self):
        self._lock = threading.Lock()

        #List of all observers that are listening for events
        self._observers = []

    def subscribe(self, observer):
        #When the observer subscribes, we add it safely under the lock
        with self._lock:
            self._observers.append(observer)

    def publish(self, event: str, **data):
        #When an important event happens, announce it
        with self._lock:
            observers = list(self._observers)
        for obs in observers:

            #Look for a function that matches the event
            handler = getattr(obs, f"on_{event}", None)

            #If the observer has that function run it
            if callable(handler):
                handler(**data)


class PolicyReporterObserver:
    def __init__(self):
        self._last_policy_by_country = {}

    def on_policy_change(self, country, day, new_policy_name: str):
        prev = self._last_policy_by_country.get(country.name)
        if prev is None:

            #If this is the first time we see the country’s policy, we simply print the initial policy.
            print(f"   • {country.name}: política inicial = {new_policy_name}")
        elif prev != new_policy_name:
            print(f"   • {country.name}: {prev} → {new_policy_name}")

        #Update the stored policy so we can detect future changes.
        self._last_policy_by_country[country.name] = new_policy_name
