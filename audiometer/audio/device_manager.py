import sounddevice as sd
from typing import Optional, List

try:
    # Optional: Windows Core Audio via pycaw for stable endpoint IDs
    from pycaw.pycaw import AudioUtilities
except Exception:  # pragma: no cover
    AudioUtilities = None

class AudioDeviceManager:
    def __init__(self):
        self.output_device: Optional[str] = None
        self.output_index: Optional[int] = None
        self.output_uid: Optional[str] = None

    def list_output_devices(self) -> List[str]:
        try:
            devices = sd.query_devices()
        except Exception:
            return []
        outs = []
        for d in devices:
            try:
                if d.get("max_output_channels", 0) >= 2 and d.get("name"):
                    outs.append(d["name"])  # show friendly names
            except Exception:
                continue
        return outs

    def _find_device_index(self, name: str) -> Optional[int]:
        """Find output device index by friendly name.
        Matches exact first, then case-insensitive, then startswith/contains.
        Only devices with >=2 output channels are eligible.
        """
        try:
            devices = sd.query_devices()
        except Exception:
            return None

        candidates = [
            (i, d)
            for i, d in enumerate(devices)
            if d.get("max_output_channels", 0) >= 2 and d.get("name")
        ]
        # exact match
        for i, d in candidates:
            if d["name"] == name:
                return i
        lname = name.lower()
        # case-insensitive
        for i, d in candidates:
            if d["name"].lower() == lname:
                return i
        # startswith
        for i, d in candidates:
            if d["name"].lower().startswith(lname):
                return i
        # contains
        for i, d in candidates:
            if lname in d["name"].lower():
                return i
        return None

    def set_output_device_by_name(self, name: str):
        idx = self._find_device_index(name)
        if idx is None:
            raise ValueError(f"Dispositivo di uscita non trovato o non stereo: {name}")
        # Set PortAudio defaults: (input, output), 2 output channels by convention
        try:
            sd.default.device = (None, idx)
            sd.default.channels = 2  # force stereo stream
        except Exception:
            # Some backends only accept scalar for channels
            try:
                sd.default.channels = (0, 2)
            except Exception:
                pass
        self.output_device = name
        self.output_index = idx
        self.output_uid = self._compute_uid_for_index(idx)
        return idx

    # ---- UID helpers ----
    def _device_info(self, idx: int):
        try:
            devs = sd.query_devices()
            if 0 <= idx < len(devs):
                return devs[idx]
        except Exception:
            return None
        return None

    def _hostapi_name(self, hostapi_index: int) -> Optional[str]:
        try:
            apis = sd.query_hostapis()
            if 0 <= hostapi_index < len(apis):
                return apis[hostapi_index].get('name')
        except Exception:
            return None
        return None

    @staticmethod
    def _slugify(text: str) -> str:
        import re
        s = re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_")
        return s[:48] or "device"

    def _compute_uid_for_index(self, idx: int) -> Optional[str]:
        # Prefer Windows endpoint UID if available
        uid = self._compute_windows_uid_by_name(self.output_device or "")
        if uid:
            return uid
        info = self._device_info(idx)
        if not info:
            return None
        hostapi_name = self._hostapi_name(int(info.get('hostapi', -1)))[0:16] if self._hostapi_name(int(info.get('hostapi', -1))) else "host"
        name = info.get('name') or "device"
        return f"{self._slugify(hostapi_name)}__{self._slugify(name)}"

    # ---- Windows endpoint UID (best effort cross‑PC) ----
    def _compute_windows_uid_by_name(self, name: str) -> Optional[str]:
        if AudioUtilities is None or not name:
            return None
        try:
            devs = AudioUtilities.GetAllDevices()
        except Exception:
            return None
        name_l = name.lower()
        best = None
        for d in devs:
            try:
                dn = (d.FriendlyName or "").lower()
            except Exception:
                continue
            if dn == name_l or dn.startswith(name_l) or name_l in dn:
                best = d
                break
        if not best:
            return None
        # Inspect properties for hardware IDs
        try:
            props = getattr(best, 'properties', None) or {}
        except Exception:
            props = {}

        def _find_prop(keys: List[str]):
            for k, v in (props.items() if hasattr(props, 'items') else []):
                ks = str(k)
                for t in keys:
                    if t in ks:
                        return v
            return None

        hwids = _find_prop(['HardwareIds', 'DEVPKEY_Device_HardwareIds'])
        instid = _find_prop(['DeviceInstanceId', 'DEVPKEY_Device_InstanceId'])
        contid = _find_prop(['ContainerId'])

        # Parse patterns
        import re
        if hwids:
            first = hwids[0] if isinstance(hwids, (list, tuple)) and hwids else hwids
            s = str(first)
            m = re.search(r'VID[_-]?([0-9A-Fa-f]{4}).*PID[_-]?([0-9A-Fa-f]{4})', s)
            sn = None
            msn = re.search(r'SN[_-]?([A-Za-z0-9]{3,})', s)
            if msn:
                sn = msn.group(1)
            if m:
                vid, pid = m.group(1).upper(), m.group(2).upper()
                base = f"USB_VID{vid}_PID{pid}"
                if sn:
                    base += f"_SN{self._slugify(sn)}"
                return base
            if s.upper().startswith('BTH') or 'BTHENUM' in s.upper():
                # Bluetooth stack, try MAC
                mm = re.search(r'([0-9A-F]{2}[:\-]){5}([0-9A-F]{2})', s, re.I)
                if mm:
                    mac = mm.group(0).replace('-',':').upper()
                    return f"BT_MAC_{mac}"
        if instid:
            return f"PNP_{self._slugify(str(instid))}"
        if contid:
            return f"CONT_{self._slugify(str(contid))}"
        # Fallback: endpoint id (not guaranteed cross‑PC)
        try:
            return f"ENDPOINT_{self._slugify(best.id)}"
        except Exception:
            return None

    def get_current_output_uid(self) -> Optional[str]:
        if self.output_uid:
            return self.output_uid
        if self.output_index is not None:
            return self._compute_uid_for_index(self.output_index)
        return None
