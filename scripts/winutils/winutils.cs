// winutils.exe — minimal Windows shim cho Hadoop/Spark tren Windows.
//
// Hadoop 3.x (org.apache.hadoop.util.Shell) goi `winutils.exe` de lam cac
// thao tac POSIX nhu chmod/chown/symlink. Tren Windows ban co the dung
// "hadoop-tools" cua Apache, nhung binary nay khong co san trong
// Maven Central nen bo cuc bo tep -> tao shim nay.
//
// Chi dung cho Spark Structured Streaming tren Windows (local mode):
//   - chmod   : bo qua (NTFS khong phan biet POSIX mode)
//   - chown   : bo qua
//   - ls -F   : in duong dan
//   - symlink : tao symbolic link bang System.IO
//   - readlink: doc symbolic link
//   - groups / task: hien thi thong tin
//
// Build:  csc /nologo /target:exe /out:winutils.exe winutils.cs

using System;
using System.IO;
using System.Runtime.InteropServices;

internal static class NativeMethods
{
    // CreateSymbolicLinkW: SYMBOLIC_LINK_FLAG_DIRECTORY = 0x1
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CreateSymbolicLinkW(string lpSymlinkFileName, string lpTargetFileName, int dwFlags);

    public static void CreateSymbolicLink(string link, string target)
    {
        bool isDir = Directory.Exists(target);
        bool ok = CreateSymbolicLinkW(link, target, isDir ? 0x1 : 0x0);
        if (!ok)
        {
            int err = Marshal.GetLastWin32Error();
            throw new IOException("CreateSymbolicLink failed, win32 error " + err);
        }
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetFinalPathNameByHandleW(IntPtr h, System.Text.StringBuilder path, uint len, uint flags);

    public static string ReadSymbolicLink(string path)
    {
        // Doc link target bang FileInfo.LinkTarget khong co san tren .NET Framework 4.x,
        // nen dung P/Invoke: CreateFile voi FILE_FLAG_OPEN_REPARSE_POINT + DeviceIoControl FSCTL_GET_REPARSE_POINT.
        try
        {
            var info = new FileInfo(path);
            if (!info.Attributes.HasFlag(FileAttributes.ReparsePoint)) return null;
            return NativeLink.GetTarget(path);
        }
        catch { return null; }
    }
}

internal static class NativeLink
{
    private const uint FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000;
    private const uint FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;
    private const uint GENERIC_READ = 0x80000000;
    private const uint FSCTL_GET_REPARSE_POINT = 0x000900A8;
    private const uint IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003;
    private const uint IO_REPARSE_TAG_SYMLINK = 0xA000000C;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateFileW(string name, uint access, uint share, IntPtr sec, uint creation, uint flags, IntPtr template);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr h);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool DeviceIoControl(IntPtr h, uint code, IntPtr inBuf, uint inSize, byte[] outBuf, uint outSize, out uint bytes, IntPtr overlapped);

    public static string GetTarget(string path)
    {
        IntPtr h = CreateFileW(path, GENERIC_READ, 0, IntPtr.Zero, 3, FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS, IntPtr.Zero);
        if (h == new IntPtr(-1)) return null;
        try
        {
            byte[] buf = new byte[16 * 1024];
            uint returned;
            if (!DeviceIoControl(h, FSCTL_GET_REPARSE_POINT, IntPtr.Zero, 0, buf, (uint)buf.Length, out returned, IntPtr.Zero))
                return null;

            uint tag = BitConverter.ToUInt32(buf, 0);
            if (tag != IO_REPARSE_TAG_SYMLINK && tag != IO_REPARSE_TAG_MOUNT_POINT) return null;

            // REPARSE_DATA_BUFFER: header 8 byte, SubstituteNameOffset uint16 @ 8, ... PrintNameOffset uint16 @ 10
            uint substOff = BitConverter.ToUInt16(buf, 8);
            uint substLen = BitConverter.ToUInt16(buf, 10);
            uint printOff = BitConverter.ToUInt16(buf, 12);
            uint printLen = BitConverter.ToUInt16(buf, 14);

            string target = System.Text.Encoding.Unicode.GetString(buf, (int)printOff, (int)printLen);
            return target.TrimEnd('\0');
        }
        finally { CloseHandle(h); }
    }
}

internal static class WinUtils
{
    private static int Main(string[] args)
    {
        if (args.Length == 0)
        {
            Console.Error.WriteLine("Usage: winutils <command> [args...]");
            return 1;
        }

        string cmd = args[0];
        string[] rest = new string[args.Length - 1];
        Array.Copy(args, 1, rest, 0, rest.Length);

        try
        {
            switch (cmd)
            {
                case "chmod":
                    // No-op: NTFS khong co POSIX permission bit.
                    return 0;

                case "chown":
                    return 0;

                case "ls":
                    for (int i = 0; i < rest.Length; i++)
                    {
                        if (rest[i].StartsWith("-")) continue;
                        Console.WriteLine(rest[i]);
                    }
                    return 0;

                case "symlink":
                    // winutils symlink <link> <target>
                    if (rest.Length < 2) return 1;
                    if (Directory.Exists(rest[0])) Directory.Delete(rest[0], true);
                    if (File.Exists(rest[0])) File.Delete(rest[0]);
                    string parent = Path.GetDirectoryName(Path.GetFullPath(rest[0]));
                    if (!string.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
                    NativeMethods.CreateSymbolicLink(rest[0], rest[1]);
                    return 0;

                case "readlink":
                    if (rest.Length < 1) return 1;
                    string target = NativeMethods.ReadSymbolicLink(rest[0]);
                    if (!string.IsNullOrEmpty(target)) Console.WriteLine(target);
                    return 0;

                case "groups":
                    Console.WriteLine("BUILTIN\\Users");
                    return 0;

                case "task":
                    // task isAlive <pid> / task kill <pid>
                    if (rest.Length >= 2 && rest[0] == "isAlive")
                    {
                        int pid;
                        if (!int.TryParse(rest[1], out pid)) return 1;
                        try
                        {
                            System.Diagnostics.Process.GetProcessById(pid);
                            return 0;
                        }
                        catch { return 1; }
                    }
                    return 0;

                default:
                    // Unknown command: succeed quietly so Hadoop khong abort.
                    return 0;
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("winutils: " + ex.Message);
            return 1;
        }
    }
}
