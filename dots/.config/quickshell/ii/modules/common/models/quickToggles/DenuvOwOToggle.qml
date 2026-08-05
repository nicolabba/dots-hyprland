import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.services
import qs.modules.common
import qs.modules.common.functions
import qs.modules.common.widgets

QuickToggleModel {
    // Internal on/off state. Kept in sync with the real module state on
    // startup: cpuid_fault_emulation loaded  =>  ON.
    property bool _on: false

    name: Translation.tr("DenuvOwO")
    // AndroidDenuvOwOToggle asks AndroidQuickToggleButton to render this as a
    // compact text icon instead of a Material Symbols glyph.
    icon: "OwO"
    toggled: _on
    tooltipText: Translation.tr("Enable DenuvOwO support")

    mainAction: () => {
        _on = !_on
        // No sudo prompt: the script elevates via sudo, allowed by the
        // scoped sudoers rule (/etc/sudoers.d/denuvowo) for THIS script
        // only. Enable/disable commands live in /usr/local/bin/denuvowo.
        const cmds = _on
            ? "/usr/local/bin/denuvowo enable"
            : "/usr/local/bin/denuvowo disable"
        Quickshell.execDetached(["sh", "-c", cmds])
    }

    // Sync initial visual state from the actual loaded module.
    Process {
        running: true
        command: ["sh", "-c", "lsmod | grep -q cpuid_fault_emulation"]
        onExited: (exitCode, exitStatus) => { _on = (exitCode === 0) }
    }
}
