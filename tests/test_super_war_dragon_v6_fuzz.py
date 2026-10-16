"""Deterministic randomized fuzz for 400 synthetic player-view Red Alert observations."""
import random
from types import SimpleNamespace
from altruagent import WAIT
from examples.fast_redalert_agent_v6 import FastRedAlertV6


def test_random_legal_batches():
    rng=random.Random(31803)
    failures=[]
    for i in range(400):
        cash=rng.choice([0,150,400,1000,1800,2500,4500,6500])
        ore=rng.choice([0,0,350,1200,3000])
        built=rng.sample(["fact","powr","barr","proc","weap","fix","powr","proc"], k=rng.randint(1,8))
        if "fact" not in built: built.append("fact")
        units=[{"type":rng.choice(["e1","e3","harv","1tnk","2tnk"]),
                "id":500+j,"x":rng.randrange(5,90),"y":rng.randrange(5,90),
                "idle":rng.choice([True,False]),"act":rng.choice(["Idle","AttackMove","FindAndDeliverResources"])}
               for j in range(rng.randint(0,70))]
        if rng.random()<0.45:
            enemies=[{"type":"e1","id":1000,"x":rng.randrange(2,95),"y":rng.randrange(2,95)}]
        else: enemies=[]
        readyitem=rng.choice(["proc","weap","powr","barr",None])
        queued=([{"queue":"Building","item":readyitem,"ready":True}] if readyitem else [])
        obs={"tick":i*21,"economy":{"cash":cash,"ore":ore,
              "power_provided":rng.choice([0,100,200,300]),"power_drained":rng.randrange(0,300)},
             "buildings":[{"type":x,"id":200+j,"x":12+j,"y":14,
                           "hp":rng.randrange(20,101)} for j,x in enumerate(built)],
             "units":units,"production":queued,"base_center":[20,20],
             "visible_enemies":enemies,"visible_enemy_buildings":[]}
        legal={"build":["powr","proc","weap","barr","fix"],"train":["e1","e3","harv","apc","1tnk","2tnk"],
               "place":[readyitem] if readyitem else [],
               "repair":[200],"enemy_base":[80,80],"deploy":[]}
        ctx=SimpleNamespace(game_type="red_alert",game_config={})
        state=SimpleNamespace(raw={"phase":"playing","observation":obs,
              "legal_actions":legal,"map":{"bounds":[0,0,96,96]}},legal_actions=[])
        agent=FastRedAlertV6()
        try:
            act=agent.choose_action(state,ctx)
            if act is WAIT:continue
            commands=act.action["orders"]
            assert len(commands)<=20
            assert sum(len(x.get("units",[])) if x.get("units") else 1 for x in commands)<=200
            for command in commands:
                assert command["cmd"] in {"deploy","build","place","train","harvest","attack_move","repair"}
                if "units" in command:
                    assert len(command["units"]) == len(set(command["units"]))
                    assert all(type(n) is int for n in command["units"])
                if command["cmd"] == "build":
                    assert command["item"] in legal["build"]
                if command["cmd"] == "train":
                    assert command["item"] in legal["train"]
        except Exception as exc:failures.append((i,str(exc)[:130]))
    assert not failures, failures[:8]
