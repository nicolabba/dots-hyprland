"""Run with python -m unittest discover -s tests -v (requires qs)."""
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import tempfile
import time
import unittest


class WeatherPositioningTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("qs"), "Quickshell is required")
    def test_disabled_gps_does_not_construct_position_source(self):
        source = (Path(__file__).resolve().parents[1]
                  / "dots/.config/quickshell/ii/services/Weather.qml")
        text = source.read_text()
        start = text.find("    Loader {\n        id: positioningLoader")
        if start < 0:
            start = text.index("    PositionSource {")
        end = text.index("{", start) + 1
        depth = 1
        while depth:
            depth += (text[end] == "{") - (text[end] == "}")
            end += 1
        # Exercise the actual declaration without starting unrelated shell services.
        fragment = text[start:end].replace(
            "id: positionSource",
            'id: positionSource\n Component.onCompleted: console.log("SOURCE_CONSTRUCTED")',
        )
        qml = '''import QtQuick
import QtPositioning
import Quickshell
ShellRoot {
 id: root
 property bool gpsActive: false
 property int fetchInterval: 600000
 property var location: ({valid: false})
 function getData() {}
''' + fragment + '''
 Timer { interval: 100; running: true; onTriggered: console.log("PROBE_READY") }
}
'''
        with tempfile.TemporaryDirectory(prefix="weather-positioning-") as directory:
            probe = Path(directory) / "shell.qml"
            probe.write_text(qml)
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            process = subprocess.Popen(
                ["qs", "-p", str(probe), "--no-color"], env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            assert process.stdout is not None
            lines = []
            started = time.monotonic()
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    while time.monotonic() - started < 60:
                        if not selector.select(timeout=0.1):
                            if process.poll() is not None:
                                break
                            continue
                        line = process.stdout.readline()
                        if not line:
                            break
                        lines.append(line)
                        if "PROBE_READY" in line:
                            break
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                process.stdout.close()
            output = "".join(lines)
            self.assertIn("PROBE_READY", output, output)
            self.assertNotIn("SOURCE_CONSTRUCTED", output,
                             "GPS disabled still constructs the location backend:\n" + output)
            self.assertLess(time.monotonic() - started, 5, output)


if __name__ == "__main__":
    unittest.main()
