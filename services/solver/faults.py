"""故障开关（D3）：环境变量控制，默认全部关闭。

每个开关在 /health 中不显示；进程启动时读取一次，运行中不可改（需重启生效）。
"""
import os


def _flag(name: str, default: str = "off") -> bool:
    return os.environ.get(name, default).strip().lower() == "on"


class Faults:
    """读取 4 个故障开关。默认值保证"默认是一个正确、诚实的求解器"。"""

    def __init__(self) -> None:
        # 关闭稳定性保护：允许 r > 0.5 静默进入不稳定区（默认开启保护 -> off 时才允许越界）
        self.cfl_guard_off: bool = _flag("QBC_FAULT_CFL_GUARD")
        # 共享状态：求解器复用进程级共享数组（默认按请求隔离）
        self.shared_state: bool = _flag("QBC_FAULT_SHARED_STATE")
        # 静默钳制：负 alpha 不报 400，静默取绝对值
        self.silent_clamp: bool = _flag("QBC_FAULT_SILENT_CLAMP")
        # 超时返回部分结果但不标记 incomplete
        self.partial_on_timeout: bool = _flag("QBC_FAULT_PARTIAL_ON_TIMEOUT")

    def snapshot(self) -> dict:
        return {
            "QBC_FAULT_CFL_GUARD": "off" if self.cfl_guard_off else "on",
            "QBC_FAULT_SHARED_STATE": "on" if self.shared_state else "off",
            "QBC_FAULT_SILENT_CLAMP": "on" if self.silent_clamp else "off",
            "QBC_FAULT_PARTIAL_ON_TIMEOUT": "on" if self.partial_on_timeout else "off",
        }


FAULTS = Faults()
