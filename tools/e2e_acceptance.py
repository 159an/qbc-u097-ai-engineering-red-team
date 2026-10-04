# -*- coding: utf-8 -*-
"""QBC / U097 端到端自检（14 项，纯标准库，无第三方依赖）。

用法（仓库根目录，需先 scripts\\start-all.ps1 起服务）：
    python tools/e2e_acceptance.py

行为：
  - 开始时探测 127.0.0.1:8081/8082 两个 /health，任一不可用则打印提示并 exit 1；
  - 逐条打印 PASS/FAIL <项名> [细节]，末尾打印「通过 N / 14」；
  - 全过 exit 0，否则 exit 1。

期望值独立推导（不从被测实现抄）：
  - 对流稳态三格式（ftcs/btcs/cn）对照**解析解**（连续对流扩散指数解）
    u(x) = (exp(Pe*x)-1)/(exp(Pe)-1)，Pe = v*L/alpha = 1（L=1, v=1, alpha=1）：
      x=0.25 -> 0.165296, x=0.50 -> 0.377541, x=0.75 -> 0.650068
    允许 2e-4 数值离散偏差（dx=0.05，二阶精度量级）。
"""
import json
import math
import sys
import threading
import urllib.error
import urllib.request

SOLVER = "http://127.0.0.1:8081"
ORACLE = "http://127.0.0.1:8082"


def _post(url, body):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, None
    except Exception as e:  # 连接失败等
        return -1, str(e)


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, None
    except Exception as e:
        return -1, str(e)


def solve(**kw):
    nodes = kw.get("nodes", 21)
    alpha = kw.get("alpha", 1.0)
    length = kw.get("length", 1.0)
    dt = kw.get("dt")
    if dt is None:
        dx = length / max(1, (nodes - 1))
        dt = 0.4 * dx * dx / abs(alpha if alpha else 1.0)
    base = {
        "alpha": alpha, "nodes": nodes, "dt": dt, "tEnd": 0.05, "length": length,
        "scheme": "ftcs", "probes": [0.5], "recordEvery": 10,
        "boundary": {"left": {"kind": "dirichlet", "value": 0.0},
                     "right": {"kind": "dirichlet", "value": 0.0}},
        "initial": {"kind": "sin", "amplitude": 1.0, "modes": 1},
    }
    base.update(kw)
    return _post(SOLVER + "/solve", base)


def pick(obj, *paths):
    for path in paths:
        cur, ok = obj, True
        for key in path.split("."):
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok:
            return cur
    return None


def scrub(obj):
    """去掉请求级不变量（id / 时间戳 / 耗时），只留数值结果，用于并发一致性比较。"""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()
                if not any(tag in k.lower() for tag in ("id", "time", "elapsed", "duration"))}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


# ---- 前置：两个 /health 探针 ---------------------------------------------
def health_precheck():
    s1, _ = _get(SOLVER + "/health")
    s2, _ = _get(ORACLE + "/health")
    ok = s1 == 200 and s2 == 200
    print("[precheck] solver /health status=%s, oracle /health status=%s" % (s1, s2))
    if not ok:
        print("FAIL: 服务未就绪（需先 scripts\\start-all.ps1 起 solver 8081 / oracle 8082），"
              "无法执行 14 项自检。")
        sys.exit(1)


ROWS = []


def chk(name, ok, detail=""):
    ROWS.append((name, bool(ok), str(detail)))


def run_checks():
    # ---- D1：求解服务（8081） --------------------------------------------
    st, b = solve(nodes=2)
    chk("D1-1 nodes=2 不崩溃且 200", st == 200 and isinstance(b, dict), "status=%s" % st)

    st, b = solve(nodes=1)
    chk("D1-1b nodes=1 -> 400", st == 400, "status=%s" % st)

    st, b = solve(alpha=-1.0)
    chk("D1-2 alpha=-1 -> 400", st == 400, "status=%s" % st)

    st, b = solve(tEnd=0.0)
    chk("D1-3 tEnd=0 -> 200", st == 200, "status=%s" % st)

    st, b = solve(nodes=21, tEnd=0.05)  # dt 按 0.4*r 上限设定，r=0.4 稳定域内
    bu = pick(b, "summary.blowUp", "blowUp") if isinstance(b, dict) else None
    chk("D1-4 r=0.4 稳定 (blowUp=False)", st == 200 and bu is False,
        "status=%s blowUp=%s" % (st, bu))

    dx = 1.0 / 20
    st, b = solve(nodes=21, tEnd=0.05, dt=0.51 * dx * dx)  # r = 0.51 > 0.5，超稳定域
    bu = pick(b, "summary.blowUp", "blowUp") if isinstance(b, dict) else None
    chk("D1-5 r=0.51 被守卫拦 (blowUp=True)", st == 200 and bu is True,
        "status=%s blowUp=%s" % (st, bu))

    outs = [None] * 10

    def worker(i):
        st2, b2 = solve(nodes=21, tEnd=0.05)
        outs[i] = json.dumps(scrub(b2), sort_keys=True) if isinstance(b2, dict) else "ERR%s" % st2

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    distinct = len(set(outs))
    chk("D1-6 10 并发逐位一致（仅数值字段）", distinct == 1, "distinct=%d" % distinct)

    # 对流稳态：解析解（连续）u(x)=(exp(Pe*x)-1)/(exp(Pe)-1), Pe=v*L/alpha=1
    # x=0.25/0.50/0.75 -> 0.165296/0.377541/0.650068（独立推导，非抄自被测输出）
    pe = 1.0
    want_analytic = [(math.exp(pe * x) - 1) / (math.exp(pe) - 1) for x in (0.25, 0.5, 0.75)]

    for scheme in ("ftcs", "btcs", "cn"):
        st, b = solve(nodes=21, length=1.0, tEnd=3.0, scheme=scheme,
                      probes=[0.25, 0.5, 0.75],
                      boundary={"left": {"kind": "dirichlet", "value": 0.0},
                                "right": {"kind": "dirichlet", "value": 1.0}},
                      advection={"enabled": True, "velocity": 1.0})
        probes = pick(b, "probes") if isinstance(b, dict) else None
        vals = [p["points"][-1]["u"] for p in (probes or [])]
        ok = (st == 200 and len(vals) == 3
              and all(abs(v - w) < 2e-4 for v, w in zip(vals, want_analytic)))
        chk("D1-7 对流稳态 %s（解析 0.165296/0.377541/0.650068）" % scheme,
            ok, "got=%s" % (["%.6f" % v for v in vals] if vals else st))

    # ---- D2：解析解 Oracle（8082） ---------------------------------------
    st, _ = _get(ORACLE + "/health")
    chk("D2-1 oracle /health -> 200", st == 200, "status=%s" % st)

    st, _ = _post(ORACLE + "/exact", {
        "alpha": 1.0, "length": 1.0,
        "initial": {"kind": "sin", "amplitude": 1.0, "modes": 1},
        "boundary": {"left": {"kind": "dirichlet", "value": 0.0},
                     "right": {"kind": "dirichlet", "value": 0.0}},
        "points": [{"x": 0.5, "t": 0.05}],
    })
    chk("D2-2 有闭式解 -> 200", st == 200, "status=%s" % st)

    st, _ = _post(ORACLE + "/exact", {
        "alpha": 1.0, "length": 1.0,
        "initial": {"kind": "sin", "amplitude": 1.0, "modes": 1},
        "boundary": {"left": {"kind": "dirichlet", "value": 0.0},
                     "right": {"kind": "dirichlet", "value": 1.0}},
        "points": [{"x": 0.5, "t": 0.05}],
    })
    chk("D2-3 无闭式解 -> 422（不冒充数值解）", st == 422, "status=%s" % st)

    st, _ = _post(ORACLE + "/exact", {
        "alpha": -1.0, "length": 1.0,
        "points": [{"x": 0.5}],
    })
    chk("D2-4 alpha<=0 -> 400", st == 400, "status=%s" % st)


def main():
    health_precheck()
    run_checks()
    total = len(ROWS)
    passed = sum(1 for _, ok, _ in ROWS if ok)
    print("=" * 70)
    print("QBC/U097 端到端自检（solver 8081 / oracle 8082，纯标准库、无 LLM）")
    print("=" * 70)
    for name, ok, detail in ROWS:
        line = ("PASS" if ok else "FAIL") + "  " + name
        if detail:
            line += "   [" + detail + "]"
        print(line)
    print("-" * 70)
    print("通过 %d / %d" % (passed, total))
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()