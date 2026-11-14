import QtQuick
import "SpotifyLogic.js" as Logic

// Incremental ListModel keeps existing delegates and the user's flick position.
ListView {
    id: root
    property var entries: []
    property bool pagingActive: false
    property bool authorized: false
    property bool busy: false
    property bool blocked: false
    property var nextOffset: null
    property var requestedOffset: null
    signal fetchNext()
    model: ListModel { id: records }

    function syncEntries() {
        // A new query/category first publishes an empty array from the backend.
        if (entries.length < records.count || (entries.length && records.count && entries[0].uri !== records.get(0).uri)) {
            records.clear();
            requestedOffset = null;
            positionViewAtBeginning();
        }
        if (!entries.length) requestedOffset = null;
        for (let i = records.count; i < entries.length; i++) records.append(entries[i]);
        pagination.restart();
    }
    function checkPage() {
        if (requestedOffset === nextOffset) return;
        if (Logic.shouldFetchNext({active: pagingActive, authorized: authorized, busy: busy, blocked: blocked,
            next: nextOffset, contentY: contentY, originY: originY, contentHeight: contentHeight, height: height})) {
            requestedOffset = nextOffset;
            fetchNext();
        }
    }
    onEntriesChanged: syncEntries()
    onContentYChanged: pagination.restart()
    onContentHeightChanged: pagination.restart()
    onHeightChanged: pagination.restart()
    onPagingActiveChanged: pagination.restart()
    onAuthorizedChanged: pagination.restart()
    onBusyChanged: pagination.restart()
    onBlockedChanged: pagination.restart()
    onNextOffsetChanged: pagination.restart()
    Timer { id: pagination; interval: 80; onTriggered: root.checkPage() }
}
