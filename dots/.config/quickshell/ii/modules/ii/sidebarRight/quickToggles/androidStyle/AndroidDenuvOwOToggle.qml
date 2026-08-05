import qs.modules.common
import qs.modules.common.models.quickToggles
import QtQuick

AndroidQuickToggleButton {
    toggleModel: DenuvOwOToggle {}
    buttonIconIsText: true
    textIconSize: expandedSize ? 15 : 17
}
