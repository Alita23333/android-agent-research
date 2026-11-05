package dev.alita.androidagent;

import android.database.Cursor;
import android.database.MatrixCursor;
import android.os.Build;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract.Document;
import android.provider.DocumentsContract.Root;
import android.provider.DocumentsProvider;
import org.json.JSONObject;
import java.io.File;
import java.io.FileNotFoundException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Test APK only. Java/platform APIs because a standalone test provider has no target Kotlin loader. */
public class SkillFixtureDocumentsProvider extends DocumentsProvider {
    private File directory() { return new File(getContext().getFilesDir(), "skill-ui-documents"); }
    @Override public boolean onCreate() {
        if (TestDeviceTarget.matchingKnownDevice() == null) return true;
        try {
            File directory = directory(); directory.mkdirs();
            File identity = new File(directory, "identity.json");
            if (identity.exists()) return true;
            String id = "ui-proof-" + System.currentTimeMillis();
            String[] names = {"01-skill-v1.zip", "02-skill-v2.zip", "03-missing.zip"};
            String[] revisions = {"1", "2", "missing"};
            for (int i = 0; i < names.length; i++) {
                String revision = revisions[i];
                String name = "missing".equals(revision) ? id + "-missing" : id;
                try (ZipOutputStream zip = new ZipOutputStream(Files.newOutputStream(new File(directory, names[i]).toPath()))) {
                    entry(zip, "SKILL.md", "---\nname: " + name + "\ndescription: Read an immutable reference for a controlled UI acceptance task\nversion: " + revision + "\n---\nRead references/rule.txt using Read. Reply with the exact resource line. Do not write files or use other tools.\n");
                    entry(zip, "references/rule.txt", "UI_RESOURCE_" + id + "_" + revision + "\n");
                    if ("missing".equals(revision)) entry(zip, "android.yaml", "runtimes: [python]\npermissions: [root]\n");
                }
            }
            Files.write(identity.toPath(), new JSONObject().put("id", id).toString().getBytes(StandardCharsets.UTF_8));
            return true;
        } catch (Exception e) { throw new IllegalStateException("Test fixture creation failed", e); }
    }
    private static void entry(ZipOutputStream zip, String path, String text) throws java.io.IOException {
        zip.putNextEntry(new ZipEntry(path)); zip.write(text.getBytes(StandardCharsets.UTF_8)); zip.closeEntry();
    }
    @Override public Cursor queryRoots(String[] projection) {
        String[] columns = projection == null ? new String[]{Root.COLUMN_ROOT_ID, Root.COLUMN_DOCUMENT_ID, Root.COLUMN_TITLE, Root.COLUMN_FLAGS, Root.COLUMN_MIME_TYPES} : projection;
        MatrixCursor cursor = new MatrixCursor(columns);
        if (!new File(directory(), "identity.json").isFile()) return cursor;
        MatrixCursor.RowBuilder row = cursor.newRow();
        for (String key : columns) {
            Object value = null;
            if (Root.COLUMN_ROOT_ID.equals(key)) value = "fixtures";
            else if (Root.COLUMN_DOCUMENT_ID.equals(key)) value = "root";
            else if (Root.COLUMN_TITLE.equals(key)) value = "Agent test fixtures";
            else if (Root.COLUMN_FLAGS.equals(key)) value = Root.FLAG_LOCAL_ONLY;
            else if (Root.COLUMN_MIME_TYPES.equals(key)) value = "application/zip";
            row.add(key, value);
        }
        return cursor;
    }
    private static boolean isFile(String id) { return "01-skill-v1.zip".equals(id) || "02-skill-v2.zip".equals(id) || "03-missing.zip".equals(id); }
    private Cursor documents(String[] projection, String[] ids) throws FileNotFoundException {
        String[] columns = projection == null ? new String[]{Document.COLUMN_DOCUMENT_ID, Document.COLUMN_DISPLAY_NAME, Document.COLUMN_MIME_TYPE, Document.COLUMN_FLAGS, Document.COLUMN_SIZE} : projection;
        MatrixCursor cursor = new MatrixCursor(columns);
        for (String id : ids) {
            if (!"root".equals(id) && !isFile(id)) throw new FileNotFoundException("Unknown fixture");
            MatrixCursor.RowBuilder row = cursor.newRow();
            for (String key : columns) {
                Object value = null;
                if (Document.COLUMN_DOCUMENT_ID.equals(key)) value = id;
                else if (Document.COLUMN_DISPLAY_NAME.equals(key)) value = "root".equals(id) ? "Agent test fixtures" : id;
                else if (Document.COLUMN_MIME_TYPE.equals(key)) value = "root".equals(id) ? Document.MIME_TYPE_DIR : "application/zip";
                else if (Document.COLUMN_FLAGS.equals(key)) value = 0;
                else if (Document.COLUMN_SIZE.equals(key) && !"root".equals(id)) value = new File(directory(), id).length();
                row.add(key, value);
            }
        }
        return cursor;
    }
    @Override public Cursor queryDocument(String id, String[] projection) throws FileNotFoundException { return documents(projection, new String[]{id}); }
    @Override public Cursor queryChildDocuments(String parent, String[] projection, String sort) throws FileNotFoundException {
        if (!"root".equals(parent)) throw new FileNotFoundException("Unknown root");
        return documents(projection, new String[]{"01-skill-v1.zip", "02-skill-v2.zip", "03-missing.zip"});
    }
    @Override public ParcelFileDescriptor openDocument(String id, String mode, CancellationSignal signal) throws FileNotFoundException {
        if (!"r".equals(mode) || !isFile(id)) throw new FileNotFoundException("Read-only fixture");
        return ParcelFileDescriptor.open(new File(directory(), id), ParcelFileDescriptor.MODE_READ_ONLY);
    }
}
