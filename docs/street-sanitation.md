# Street sanitation and housing loss

Street waste is a real `WorldObject`, not an ephemeral animation. A recorded bodily
accident gives its actor a seven-stage squat animation while that object grows
into view. Once the actor leaves, the waste stays at its original position until
actual cleaning or the existing reported-hazard service removes it. It persists
through checkpoints and can be stepped on by other citizens.

The existing physiology uses one simplified `bladder` meter for restroom need.
At 99, a person who is not currently using a toilet has an accident. This applies
equally to housed and unhoused citizens. Zero cash and lack of housing are not
sanitation triggers, and no personality, hygiene preference or subsequent action
is assigned to anyone.

The fix separates creation from stepping:

- `waste` events identify their actor and `payload.object_id`; the object stores
  `created_at` and `created_by`.
- The actor pauses for 2.4 **simulated seconds**, clears the interrupted action,
  and invalidates any stale in-flight decision. Later decisions remain autonomous.
- For the first 3 **simulated seconds**, the creator does not automatically step
  in their newly created waste. Other people can step in it immediately.
- The viewer's squat/creation effect lasts 2.4 **browser seconds**, like existing
  contact animations. It can finish while the simulation is paused. Reloading
  shows the existing object without replaying old accidents; reduced motion uses
  a static squat and the full pile.

The housing mechanism is unchanged: SF rent debt accumulates, and the checked-in
scenario loses tenancy after 60 unpaid budget days. This is a game assumption,
not a legal eviction process. A newly empty wallet does not immediately remove
a person's home. The observer's selected-person caption now shows `No home`
when the authoritative home flag is absent.

## Verification

```sh
python scripts/build_sanitation_replay.py
python -m pytest tests/test_street_sanitation.py tests/test_interactions.py tests/test_sf_economy.py tests/test_checkpoint.py -q
node --test scripts/test_street_sanitation.mjs scripts/test_citizen_art.mjs scripts/test_citizen_interactions.mjs scripts/test_pixel_city.mjs
python scripts/smoke_citizen_interactions.py
```

The builder creates a temporary SF test world at the 59-day arrears boundary,
applies the existing next-day accounting, triggers the actual physiological
accident, and executes a test-supplied walking decision. It writes an observer
replay, without any LLM call or mutation of a saved preview world.

Open `http://127.0.0.1:8007/static/interaction-replay.html?scene=sanitation` on the
existing preview server. **Next interaction** advances through loss of housing,
visible relief and the waste left behind; **Replay this interaction** replays the
current recorded event. This is an explicit mechanics replay, not autonomous
LLM activity. The fixture's Alex Rivera is an invented test character.

The new `AgentState.relief_until` defaults to zero when old checkpoints are read.
Backend changes need a coordinator-managed server restart before they affect
the running world. No shared server was restarted, no old save reset, and no
model request limits or provider settings changed during this work.
