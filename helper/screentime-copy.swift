// The one program given Full Disk Access. It copies the iPhone's synced Screen Time
// records, and the list of synced devices, into the Home Screen tool's state folder,
// where ordinary scripts can read them. It reads nothing else and writes nowhere else.

import Foundation

let home = FileManager.default.homeDirectoryForCurrentUser
let biome = home.appending(path: "Library/Biome")
let appsInFocus = biome.appending(path: "streams/restricted/App.InFocus/remote")
let devices = biome.appending(path: "sync/sync.db")

// bin/homescreen-usage-install passes this repo's state/screentime folder as the one
// argument, and bakes it into the launchd job too, so the helper does not need to
// guess where it was cloned.
guard let destinationPath = CommandLine.arguments.dropFirst().first else {
    fatalError("usage: screentime-copy <destination-folder>")
}
let destination = URL(fileURLWithPath: destinationPath)

func fail(_ reason: String) -> Never {
    try? FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
    try? reason.write(to: destination.appending(path: "copy-failed"), atomically: true, encoding: .utf8)
    exit(1)
}

// macOS hides the folder from a program without Full Disk Access rather than
// refusing each file, so looking inside first is the clearest test.
if (try? FileManager.default.contentsOfDirectory(atPath: appsInFocus.path)) == nil {
    fail("no access: screentime-copy needs Full Disk Access")
}

do {
    let files = FileManager.default
    let incoming = destination.appending(path: ".incoming")
    if files.fileExists(atPath: incoming.path) { try files.removeItem(at: incoming) }
    try files.createDirectory(at: incoming, withIntermediateDirectories: true)

    try files.copyItem(at: appsInFocus, to: incoming.appending(path: "App.InFocus"))
    // SQLite keeps recent writes beside the database until it checkpoints them.
    for suffix in ["", "-wal", "-shm"] {
        let source = URL(fileURLWithPath: devices.path + suffix)
        if files.fileExists(atPath: source.path) {
            try files.copyItem(at: source, to: incoming.appending(path: "sync.db" + suffix))
        }
    }

    for name in ["App.InFocus", "sync.db", "sync.db-wal", "sync.db-shm"] {
        let target = destination.appending(path: name)
        if files.fileExists(atPath: target.path) { try files.removeItem(at: target) }
        let copied = incoming.appending(path: name)
        if files.fileExists(atPath: copied.path) { try files.moveItem(at: copied, to: target) }
    }
    try files.removeItem(at: incoming)
    try ISO8601DateFormatter().string(from: .now)
        .write(to: destination.appending(path: "copied-at"), atomically: true, encoding: .utf8)
} catch {
    fail("failed: \(error.localizedDescription)")
}
try? FileManager.default.removeItem(at: destination.appending(path: "copy-failed"))
