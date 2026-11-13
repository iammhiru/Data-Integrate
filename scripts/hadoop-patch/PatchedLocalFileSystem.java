package org.apache.hadoop.fs;

/**
 * LocalFileSystem patched cho Windows khi khong co native {@code hadoop.dll}.
 *
 * <p>Dat qua config: {@code spark.hadoop.fs.file.impl = org.apache.hadoop.fs.PatchedLocalFileSystem}
 * (xem {@code scripts/spark-conf/spark-defaults.conf}).
 *
 * @see PatchedRawLocalFileSystem
 */
public class PatchedLocalFileSystem extends LocalFileSystem {

    public PatchedLocalFileSystem() {
        super(new PatchedRawLocalFileSystem());
    }
}
