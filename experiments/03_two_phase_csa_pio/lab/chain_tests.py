"""Tests of chain.py beyond its self-test: malformed replies, the pay-once OpenAI executor (against a fake openai
module; nothing is sent), interrupts, failed-call attribution and readings. No model call.

  python experiments/03_two_phase_csa_pio/lab/chain_tests.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import types
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))


class FakeRateLimitError(Exception):
    """Stands in for openai.RateLimitError (HTTP 429): code and a response with headers."""
    def __init__(self, code=None, retry_after=None):
        super().__init__(f"429 {code}")
        self.code = code
        self.body = {"code": code}
        self.response = types.SimpleNamespace(headers={"retry-after": retry_after} if retry_after else {})


class FakeOpenAI:
    """Counts creates; each response is completed, incomplete, or still running, as the test says. mode['rate_limit']
    = n refuses the next n creates with a 429; mode['quota'] refuses them as insufficient quota."""
    log = {"create": 0, "retrieve": 0, "options": [], "refused": 0}
    mode = {"status": "completed", "crash_poll": False, "rate_limit": 0, "quota": False, "retry_after": "1",
            "create_delay": 0}

    class Resp:
        def __init__(self, rid, status):
            self.id, self.status, self.model = rid, status, "gpt-5.4"
            self.output_text = '{"conceptual assets": []}' if status == "completed" else '{"partial'
            self.incomplete_details = types.SimpleNamespace(reason="max_output_tokens") if status == "incomplete" else None
            self.usage = types.SimpleNamespace(input_tokens=100, output_tokens=50, output_tokens_details=types.SimpleNamespace(reasoning_tokens=30),
                                               input_tokens_details=types.SimpleNamespace(cached_tokens=0))

    class Responses:
        def create(self, **kw):
            if FakeOpenAI.mode["quota"]:
                FakeOpenAI.log["refused"] += 1
                raise FakeRateLimitError("insufficient_quota")
            if FakeOpenAI.mode["rate_limit"] > 0:
                FakeOpenAI.mode["rate_limit"] -= 1
                FakeOpenAI.log["refused"] += 1
                raise FakeRateLimitError("rate_limit_exceeded", retry_after=FakeOpenAI.mode["retry_after"])
            if FakeOpenAI.mode["create_delay"]:                  # a create still in flight (real wait)
                import threading
                threading.Event().wait(FakeOpenAI.mode["create_delay"])
            FakeOpenAI.log["create"] += 1
            assert kw["background"] is True and kw["metadata"]["lab_key"]
            return FakeOpenAI.Resp(f"resp_{FakeOpenAI.log['create']}", "queued")

        def retrieve(self, rid):
            FakeOpenAI.log["retrieve"] += 1
            if FakeOpenAI.mode["crash_poll"]:
                FakeOpenAI.mode["crash_poll"] = False
                raise KeyboardInterrupt("kernel stopped while waiting")
            return FakeOpenAI.Resp(rid, FakeOpenAI.mode["status"])

    def __init__(self):
        self.responses = FakeOpenAI.Responses()

    def with_options(self, **kw):
        FakeOpenAI.log["options"].append(kw)
        return self


def main(log=print) -> bool:
    sys.modules["openai"] = types.SimpleNamespace(OpenAI=FakeOpenAI, RateLimitError=FakeRateLimitError)
    import chain as CH
    import time
    time.sleep = lambda s: None
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        log(f"   {'ok  ' if cond else 'FAIL'} {label}")
    w = "neorv32_wdt"
    good1 = {"conceptual assets": [{"id": "C1", "unit": w, "objectives": ["I"], "rubric": {"integrity": "yes"},
                                    "enters through": ["bus_req_i.data"], "leaves through": [], "entry lines": [94],
                                    "held lines": [94], "exit lines": []}], "considered, not kept": []}
    good2 = {"points": [{"concept id": "C1", "point": "bus_access", "integrity": "yes", "lines": [94]}],
             "structural assets": [{"concept id": "C1", "element": "ctrl.enable", "entity": w, "label": "primary",
                                    "objectives": ["I"], "links": [], "points": ["bus_access"], "lines": [94]},
                                   {"concept id": "C1", "element": "bus_req_i.data", "entity": w, "label": "primary",
                                    "objectives": ["I"], "links": [], "points": ["bus_access"], "lines": [94]}]}

    # malformed shapes that used to crash (re-check F4, F5, F14)
    c_list_unit = [{**good1["conceptual assets"][0], "unit": [w]}]
    try:
        pr = CH.check_phase2(w, good2, c_list_unit)
        check(f"F4: a Phase 1 unit given as a list does not crash the Phase 2 check ({len(pr)} problems)", True)
    except Exception as e:  # noqa: BLE001
        check(f"F4: crashed {e!r}", False)
    try:
        a = CH.to_assets(w, {"points": [], "structural assets": [{**good2["structural assets"][0], "objectives": [["I"], {"C": 1}]}]},
                         [{"id": "C1", "objectives": [["I"]]}])
        check(f"F5: nested objectives do not crash the converter ({a['Assets'][0]['Security Objective']!r})", True)
    except Exception as e:  # noqa: BLE001
        check(f"F5: crashed {e!r}", False)
    pr1 = CH.check_phase1(w, {"conceptual assets": [{**good1["conceptual assets"][0], "held lines": 2, "enters through": {"x": 1}}]})
    check(f"F14: scalar lines and an object port list are reported ({pr1})",
          any("not a list of line numbers" in x for x in pr1) and any("neither a list nor a name" in x for x in pr1))

    # F13: anchor coverage needs the unit's own port, not a child element of the same name
    t = "neorv32_trng"
    ct = [{"id": "C1", "unit": t, "objectives": ["A"], "enters through": ["clk_i"]}]
    p2t = {"points": [{"concept id": "C1", "point": "neoTRNG_inst", "availability": "yes", "lines": []}],
           "structural assets": [{"concept id": "C1", "element": "clk_i", "entity": "neoTRNG", "label": "primary",
                                  "objectives": ["A"], "links": [], "points": ["neoTRNG_inst"], "lines": []}]}
    check("F13: the unit's anchor port is not covered by a child entity's port of the same name",
          any("anchor port 'clk_i'" in x for x in CH.check_phase2(t, p2t, ct)))

    stub_calls = []

    def stub(replies):
        def f(system, user):
            ph = 2 if "=== CONCEPTS" in user else 1
            stub_calls.append(ph)
            return json.dumps(replies[ph]), {"in": 1, "out": 1}
        return f

    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        # F2: a stored record whose check crashed is re-checked without a call
        CH.run_module("two_phase_v1", w, stub({1: good1, 2: good2}), out)
        f1 = out / "phase1" / f"{w}.json"
        rec = json.loads(f1.read_text(encoding="utf-8"))
        rec["problems"], rec["check crashed"] = ["check crashed: TypeError: x"], True
        f1.write_text(json.dumps(rec), encoding="utf-8")
        n = len(stub_calls)
        row = CH.run_module("two_phase_v1", w, stub({1: good1, 2: good2}), out)
        check(f"F2: a stored record whose check crashed is re-checked, not re-asked ({row['status']}, new calls {len(stub_calls) - n})",
              row["status"] == "done" and len(stub_calls) == n and "check crashed" not in json.loads(f1.read_text(encoding="utf-8")))
        # F6: a module that now stops leaves no stale assets file
        rec = json.loads(f1.read_text(encoding="utf-8"))
        rec["reply"], rec["problems"] = {"conceptual assets": {w: []}}, ["schema"]
        f1.write_text(json.dumps(rec), encoding="utf-8")
        row = CH.run_module("two_phase_v1", w, stub({1: good1, 2: good2}), out)
        check(f"F6: a module that stops has no assets file to score ({row['status']})",
              row["status"] == "phase 1 schema failure" and not (out / "assets" / f"{w}.json").exists())
        # STOP: no new call once an interrupt has been seen
        f1.unlink()
        CH.STOP.set()
        try:
            CH.run_module("two_phase_v1", w, stub({1: good1, 2: good2}), out)
            check("F3: STOP blocks new calls", False)
        except RuntimeError as e:
            check(f"F3: after an interrupt no new call is sent ({e})", "stopped" in str(e))
        CH.STOP.clear()

    # the pay-once executor (fake openai)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        FakeOpenAI.mode.update(status="completed", crash_poll=False)
        f = CH.openai("gpt-5.4", "high", out=out, poll=0)
        check("F12: create is not retried; polling is", {"timeout": 600, "max_retries": 0} in FakeOpenAI.log["options"]
              and {"timeout": 120, "max_retries": 5} in FakeOpenAI.log["options"])
        c0 = FakeOpenAI.log["create"]
        FakeOpenAI.mode["crash_poll"] = True
        try:
            CH.run_module("two_phase_v1", w, f, out)
        except KeyboardInterrupt:
            pass
        kept = list((out / "_pending").glob("*.json"))
        row = CH.run_module("two_phase_v1", w, f, out)
        check(f"crash while waiting, then re-run: the same response is collected (creates {FakeOpenAI.log['create'] - c0}, "
              f"pending kept {len(kept)}, status {row['status']})",
              len(kept) == 1 and FakeOpenAI.log["create"] - c0 == 1 and row["status"] == "done")
        check("F10: the pending id is removed only after the reply is on disk", not list((out / "_pending").glob("*.json"))
              and (out / "phase1" / f"{w}.json").exists())
        # F1: a pending id from another model is not collected
        g = CH.openai("gpt-5-mini", "high", out=out, poll=0)
        key = CH.sha12("S" + "\n\n" + "U")
        (out / "_pending" / f"{key}.json").write_text(json.dumps({"id": "resp_x", "model": "gpt-5.4", "effort": "high"}), encoding="utf-8")
        try:
            g("S", "U")
            check("F1: pending id of another model refused", False)
        except RuntimeError as e:
            check("F1: a pending id of another model is refused", "belongs to" in str(e))
        (out / "_pending" / f"{key}.json").unlink()
        # old-runner-07 and F8: a reply cut short is logged with its module, kept as text, and not sent again
        FakeOpenAI.mode["status"] = "incomplete"
        h = CH.openai("gpt-5.4", "high", out=out, poll=0)
        (out / "phase1" / "neorv32_spi.json").unlink(missing_ok=True)
        try:
            CH.run_module("two_phase_v1", "neorv32_spi", h, out)
        except RuntimeError:
            pass
        c1 = FakeOpenAI.log["create"]
        try:
            CH.run_module("two_phase_v1", "neorv32_spi", h, out)
            again = "sent"
        except RuntimeError as e:
            again = str(e)
        fc = CH.failed_calls(out, ["neorv32_spi"])
        check(f"old-runner-07: a reply cut short is not sent again with the same limit ({FakeOpenAI.log['create'] - c1} new creates)",
              FakeOpenAI.log["create"] == c1 and "not sent again" in again)
        check(f"F8: the failed call is attributed to its module and phase, with its partial text ({[(x['module'], x['phase'], x['reason']) for x in fc]})",
              fc and fc[0]["module"] == "neorv32_spi" and fc[0]["phase"] == 1 and fc[0]["reason"] == "max_output_tokens"
              and list((out / "_failed").glob("*.txt")) and not CH.failed_calls(out, [w]))
        FakeOpenAI.mode["status"] = "completed"
        # R1: a create refused with 429 (rate limit) is sent again; insufficient quota is not
        FakeOpenAI.mode["rate_limit"] = 2
        r0, c2 = FakeOpenAI.log["refused"], FakeOpenAI.log["create"]
        rl = CH.openai("gpt-5.4", "high", out=out, poll=0)
        text, usage = rl("S429", "U429")
        check(f"R1: a 429 rate-limit refusal is retried (refused {FakeOpenAI.log['refused'] - r0}, created {FakeOpenAI.log['create'] - c2})",
              FakeOpenAI.log["refused"] - r0 == 2 and FakeOpenAI.log["create"] - c2 == 1 and text)
        FakeOpenAI.mode["quota"] = True
        r1 = FakeOpenAI.log["refused"]
        try:
            rl("Squota", "Uquota")
            check("R2: insufficient quota is not retried", False)
        except FakeRateLimitError:
            check(f"R2: insufficient quota raises at once ({FakeOpenAI.log['refused'] - r1} refusal)", FakeOpenAI.log["refused"] - r1 == 1)
        FakeOpenAI.mode["quota"] = False

    # run_many: several runs in one pool, guards first, the one-retry rule inside the worker (stub executors)
    with tempfile.TemporaryDirectory() as td:
        real_run_dir = CH.run_dir
        CH.run_dir = lambda version, model, rep=0, effort="high": Path(td) / version / f"r{rep}"
        try:
            sent = []

            def make_call(out):
                def f(system, user):
                    ph = 2 if "=== CONCEPTS" in user else 1
                    sent.append((out.name, ph))
                    return json.dumps({1: good1, 2: good2}[ph]), {"in": 1, "out": 1}
                return f
            mods = [w, "neorv32_hwspinlock"]
            res = CH.run_many([("two_phase_v1", 0), ("two_phase_v1", 1)], mods, make_call, "stub", "high", executor="stub",
                              log=lambda *_: None)
            st = {k: [r["status"] for r in v] for k, v in res.items()}
            files = sorted(p.relative_to(td).as_posix() for p in Path(td).rglob("phase1/*.json"))
            check(f"M1: two runs in one pool, every module of each done, each in its own folder ({st}; {files})",
                  all(s == ["done", "done"] for s in st.values()) and len(files) == 4 and len(sent) == 8)
            n = len(sent)
            CH.run_many([("two_phase_v1", 0), ("two_phase_v1", 1)], mods, make_call, "stub", "high", executor="stub", log=lambda *_: None)
            check(f"M2: stored replies are not asked again in run_many ({len(sent) - n} new calls)", len(sent) == n)
            try:
                CH.run_many([("two_phase_v1", 0)], mods, make_call, "stub", "high", executor="other", log=lambda *_: None)
                check("M3: a run folder with another set-up is refused before any call", False)
            except RuntimeError as e:
                check(f"M3: a run folder with another set-up is refused before any call ({len(sent) - n} calls)",
                      "another set-up" in str(e) and len(sent) == n)
            # M4: a Phase 1 reply that fails the format check is moved and asked once more, inside the worker
            bad1 = {"conceptual assets": {w: []}}
            state = {"n": 0}

            def make_flaky(out):
                def f(system, user):
                    ph = 2 if "=== CONCEPTS" in user else 1
                    if ph == 1:
                        state["n"] += 1
                        return json.dumps(bad1 if state["n"] == 1 else good1), {"in": 1, "out": 1}
                    return json.dumps(good2), {"in": 1, "out": 1}
                return f
            res = CH.run_many([("two_phase_v1", 2)], [w], make_flaky, "stub", "high", executor="stub", log=lambda *_: None)
            row = res[("two_phase_v1", 2)][0]
            moved = Path(td) / "two_phase_v1" / "r2" / "_schema_failed" / "phase1" / f"{w}.json"
            check(f"M4: a schema failure is moved to _schema_failed and retried once ({row['status']}, retried {row.get('retried')})",
                  row["status"] == "done" and row.get("retried") and moved.exists()
                  and "asked once more" in (moved.parent.parent / "README.txt").read_text(encoding="utf-8"))

            def make_bad(out):
                return lambda system, user: (json.dumps(bad1), {"in": 1, "out": 1})
            (Path(td) / "two_phase_v1" / "r2" / "phase1" / f"{w}.json").unlink()
            res = CH.run_many([("two_phase_v1", 2)], [w], make_bad, "stub", "high", executor="stub", log=lambda *_: None)
            row = res[("two_phase_v1", 2)][0]
            check(f"M5: a module that fails again after its retry is left as it is ({row['status']})",
                  "again after its one retry" in row["status"])
        finally:
            CH.run_dir = real_run_dir
    stop_tests(CH, check, w)                         # its check() calls update ok
    return ok


def stop_tests(CH, check, w) -> None:
    """A stop during a 429 back-off, and a reload of chain followed by a re-run (the 2026-10-13 review: the back-off
    slept and then sent without looking at STOP; a reload gave old threads a new, unset STOP; a stopped run left its
    threads running). Fake openai; nothing is sent; run folders are temporary."""
    import concurrent.futures as cf
    import importlib
    import threading
    import time as _time
    pause = threading.Event().wait                  # a real wait (this file replaces time.sleep with a no-op)
    with tempfile.TemporaryDirectory() as td:
        def fake_dirs():
            CH.run_dir = lambda version, model, rep=0, effort="high": Path(td) / version / f"r{rep}"
        fake_dirs()
        try:
            # S1: a stop ends a rate-limit wait at once, and the refused request is never created
            FakeOpenAI.mode.update(rate_limit=1, retry_after="30", status="completed")
            out = Path(td) / "s1"
            f = CH.openai("gpt-5.4", "high", out=out, poll=0)
            ev, res = threading.Event(), {}

            def worker():
                threading.current_thread().lab_stop = ev
                try:
                    res["text"] = f("S-stop", "U-stop")
                except RuntimeError as e:
                    res["err"] = str(e)
            c0 = FakeOpenAI.log["create"]
            th = threading.Thread(target=worker)
            th.start()
            pause(0.5)
            t0 = _time.time()
            ev.set()
            th.join(10)
            check(f"S1: a stop ends a 30 s rate-limit wait at once ({_time.time() - t0:.2f} s; {res}); nothing created "
                  f"({FakeOpenAI.log['create'] - c0})", not th.is_alive() and _time.time() - t0 < 5
                  and "rate-limit wait" in res.get("err", "") and FakeOpenAI.log["create"] == c0)

            # S2: an interrupt of run_many while its workers wait out a 429: it returns within seconds, no worker is
            # left, nothing was created, no pending id
            FakeOpenAI.mode.update(rate_limit=100, retry_after="30")
            real_wait, calls = cf.wait, {"n": 0}

            def interrupting_wait(fs, timeout=None, return_when=cf.ALL_COMPLETED):
                calls["n"] += 1
                if calls["n"] == 1:
                    pause(0.5)                       # the workers are in their back-off now
                    calls["t"] = _time.time()        # the moment of the interrupt
                    raise KeyboardInterrupt
                return real_wait(fs, timeout=timeout, return_when=return_when)
            cf.wait = interrupting_wait
            c0, r0, t0, raised = FakeOpenAI.log["create"], FakeOpenAI.log["refused"], _time.time(), False
            mods = [w, "neorv32_hwspinlock"]
            try:
                CH.run_many([("two_phase_v1", 7)], mods, lambda out: CH.openai("gpt-5.4", "high", out=out, poll=0),
                            "gpt-5.4", "high", executor="openai", log=lambda *_: None)
            except KeyboardInterrupt:
                raised = True
            finally:
                cf.wait = real_wait
            r7 = Path(td) / "two_phase_v1" / "r7"
            took = _time.time() - calls.get("t", t0)
            left, refused = len(CH._leftover_workers()), FakeOpenAI.log["refused"] - r0
            check(f"S2: an interrupt during a 30 s 429 back-off returns {took:.1f} s after the interrupt; each worker was "
                  f"refused once and stopped inside that back-off ({refused} refusals for {len(mods)} workers); leaves "
                  f"{left} workers, creates {FakeOpenAI.log['create'] - c0}, keeps "
                  f"{len(list((r7 / '_pending').glob('*.json')))} pending ids",
                  raised and took < 5 and refused == len(mods) and left == 0
                  and FakeOpenAI.log["create"] == c0 and not list((r7 / "_pending").glob("*.json")))

            # S2b: an interrupt while a create is in flight: run_many returns only after that worker has ended, its
            # response id is kept as pending, and a re-run collects it without creating it again
            FakeOpenAI.mode.update(rate_limit=0, create_delay=2.0, status="completed")
            calls["n"] = 0
            cf.wait = interrupting_wait
            c0, raised = FakeOpenAI.log["create"], False
            try:
                CH.run_many([("two_phase_v1", 9)], [w], lambda out: CH.openai("gpt-5.4", "high", out=out, poll=0),
                            "gpt-5.4", "high", executor="openai", log=lambda *_: None)
            except KeyboardInterrupt:
                raised = True
            finally:
                cf.wait = real_wait
            r9 = Path(td) / "two_phase_v1" / "r9"
            left, kept, made = len(CH._leftover_workers()), len(list((r9 / "_pending").glob("*.json"))), FakeOpenAI.log["create"] - c0
            FakeOpenAI.mode.update(create_delay=0)
            res = CH.run_many([("two_phase_v1", 9)], [w], lambda out: CH.openai("gpt-5.4", "high", out=out, poll=0),
                              "gpt-5.4", "high", executor="openai", log=lambda *_: None)
            check(f"S2b: an interrupt during a create in flight waits for it (workers left {left}, pending kept {kept}, "
                  f"creates {made}); the re-run collects it ({FakeOpenAI.log['create'] - c0 - made} new creates, "
                  f"{res[('two_phase_v1', 9)][0]['status']})",
                  raised and left == 0 and kept == 1 and made == 1 and FakeOpenAI.log["create"] - c0 == 1
                  and res[("two_phase_v1", 9)][0]["status"] == "done")

            # S5: a stop that lands while the pool is still being filled (before the wait loop) is caught too, in
            # run_many (cell 9) and in run (cells 4, 7, 8): the started workers send nothing, and a re-run creates each
            # request once
            real_submit, sub = cf.ThreadPoolExecutor.submit, {"n": 0}
            five = CH.tuning_modules()[:5]

            def stopping_submit(self, fn, *a, **k):
                sub["n"] += 1
                if sub["n"] == 4:
                    pause(0.3)                       # the first 3 workers are in a 429 back-off now
                    raise KeyboardInterrupt
                return real_submit(self, fn, *a, **k)
            for label, rep in (("run_many", 10), ("run", 11)):
                FakeOpenAI.mode.update(rate_limit=100, retry_after="30")
                rd = CH.run_dir("two_phase_v1", "gpt-5.4", rep, "high")
                c0, r0, raised, sub["n"] = FakeOpenAI.log["create"], FakeOpenAI.log["refused"], False, 0
                cf.ThreadPoolExecutor.submit = stopping_submit
                try:
                    if label == "run_many":
                        CH.run_many([("two_phase_v1", rep)], five, lambda out: CH.openai("gpt-5.4", "high", out=out, poll=0),
                                    "gpt-5.4", "high", executor="openai", log=lambda *_: None)
                    else:
                        CH.run("two_phase_v1", five, CH.openai("gpt-5.4", "high", out=rd, poll=0), "gpt-5.4", "high",
                               rep, executor="openai", workers=5, log=lambda *_: None)
                except KeyboardInterrupt:
                    raised = True
                finally:
                    cf.ThreadPoolExecutor.submit = real_submit
                end = _time.time() + 2                       # any worker of the stopped run still alive, flag set or not
                while _time.time() < end and [t for t in threading.enumerate() if getattr(t, "lab_stop", None) and t.is_alive()]:
                    pause(0.05)
                left = len([t for t in threading.enumerate() if getattr(t, "lab_stop", None) and t.is_alive()])
                refused, made = FakeOpenAI.log["refused"] - r0, FakeOpenAI.log["create"] - c0
                FakeOpenAI.mode.update(rate_limit=0, retry_after="1")
                c1 = FakeOpenAI.log["create"]
                if label == "run_many":
                    res = CH.run_many([("two_phase_v1", rep)], five, lambda out: CH.openai("gpt-5.4", "high", out=out, poll=0),
                                      "gpt-5.4", "high", executor="openai", log=lambda *_: None)[("two_phase_v1", rep)]
                else:
                    res = CH.run("two_phase_v1", five, CH.openai("gpt-5.4", "high", out=rd, poll=0), "gpt-5.4", "high",
                                 rep, executor="openai", workers=5, log=lambda *_: None)
                keys = {json.loads(l)["key"] for l in (rd / "_keys.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
                check(f"S5 {label}: a stop while the pool fills ({refused} refusals for the 3 started workers, {left} still "
                      "alive after it, stopped or not; "
                      f"{made} creates); the re-run creates each of {len(keys)} requests once "
                      f"({FakeOpenAI.log['create'] - c1} creates, {[r['status'] for r in res]})",
                      raised and refused == 3 and left == 0 and made == 0
                      and FakeOpenAI.log["create"] - c1 == len(keys) == 5 and all(r["status"] == "done" for r in res))

            # S3: a reload of chain (cell 9's first line) does not wake a stopped run's thread, and a re-run after the
            # reload creates each request once
            importlib.reload(CH)
            fake_dirs()
            FakeOpenAI.mode.update(rate_limit=0, retry_after="1")
            old, res3 = threading.Event(), {}
            old.set()                                # a stopped run's flag

            def old_worker():
                threading.current_thread().lab_stop = old
                try:
                    res3["text"] = CH.openai("gpt-5.4", "high", out=Path(td) / "s3", poll=0)("S-old", "U-old")
                except RuntimeError as e:
                    res3["err"] = str(e)
            c0 = FakeOpenAI.log["create"]
            th = threading.Thread(target=old_worker)
            th.start()
            th.join(10)
            check(f"S3: after a reload, a stopped run's thread still sends nothing ({res3}; module STOP set: "
                  f"{CH.STOP.is_set()})", "stopped before sending" in res3.get("err", "") and FakeOpenAI.log["create"] == c0)
            res = CH.run_many([("two_phase_v1", 7)], mods, lambda out: CH.openai("gpt-5.4", "high", out=out, poll=0),
                              "gpt-5.4", "high", executor="openai", log=lambda *_: None)
            keys = [json.loads(l)["key"] for l in (r7 / "_keys.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
            st = [r["status"] for r in res[("two_phase_v1", 7)]]
            check(f"S3: the re-run after the stop and the reload creates each request once ({FakeOpenAI.log['create'] - c0} "
                  f"creates for {len(set(keys))} keys; {st})",
                  st == ["done", "done"] and FakeOpenAI.log["create"] - c0 == len(set(keys)) == 2)

            # S4: a new run refuses to start while a stopped run's worker is still finishing a request
            hold, flag = threading.Event(), threading.Event()
            flag.set()

            def busy():
                threading.current_thread().lab_stop = flag
                hold.wait(30)
            th = threading.Thread(target=busy)
            th.start()
            try:
                CH.run_many([("two_phase_v1", 8)], [w], lambda out: CH.openai("gpt-5.4", "high", out=out, poll=0),
                            "gpt-5.4", "high", executor="openai", log=lambda *_: None)
                refused = ""
            except RuntimeError as e:
                refused = str(e)
            hold.set()
            th.join(10)
            r8 = Path(td) / "two_phase_v1" / "r8"
            check(f"S4: a new run refuses while a stopped run's worker is alive, before writing anything ({refused[:60]}...)",
                  "earlier stopped run" in refused and not r8.exists())
            res = CH.run_many([("two_phase_v1", 8)], [w], lambda out: CH.openai("gpt-5.4", "high", out=out, poll=0),
                              "gpt-5.4", "high", executor="openai", log=lambda *_: None)
            check(f"S4: once that worker has ended, the run goes ahead ({[r['status'] for r in res[('two_phase_v1', 8)]]})",
                  [r["status"] for r in res[("two_phase_v1", 8)]] == ["done"])
        finally:
            importlib.reload(CH)                     # the real run_dir back
            FakeOpenAI.mode.update(rate_limit=0, retry_after="1")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if main() else 1)
