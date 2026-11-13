package org.apache.hadoop.fs;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.Arrays;

/**
 * RawLocalFileSystem patched cho Windows khi khong co native {@code hadoop.dll}.
 *
 * <p>Van de goc: {@code FileUtil.canRead(File)} -&gt; {@code NativeIO$Windows.access0(path, mode)}
 * la native method, khong co san binary Windows =&gt; {@code UnsatisfiedLinkError}.
 * Loi xuat hien khi {@code FileSystemBasedCheckpointFileManager} list thu muc checkpoint
 * cua Spark Structured Streaming.
 *
 * <p>Fix: tu doc danh sach file bang {@code File.list()} thay vi {@code FileUtil.list()},
 * va bo qua native call. Moi thay doi doc duoc dung deu dung {@code FileStatus} chuan cua Hadoop.
 */
public class PatchedRawLocalFileSystem extends RawLocalFileSystem {

    @Override
    public FileStatus[] listStatus(Path f) throws IOException {
        File localf = pathToFile(f);
        if (!localf.exists()) {
            throw new FileNotFoundException("File " + f + " does not exist");
        }
        if (!localf.isDirectory()) {
            return new FileStatus[] { getFileStatus(f) };
        }

        String[] names = localf.list();
        if (names == null) {
            throw new IOException("Invalid directory or I/O error occurred for dir: " + localf);
        }

        FileStatus[] results = new FileStatus[names.length];
        int j = 0;
        for (int i = 0; i < names.length; i++) {
            try {
                results[j] = getFileStatus(new Path(f, new Path(null, null, names[i])));
                j++;
            } catch (FileNotFoundException ignored) {
                // file bi xoa giua luc list -> bo qua
            }
        }
        return Arrays.copyOf(results, j);
    }
}
