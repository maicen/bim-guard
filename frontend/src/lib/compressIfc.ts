import { zip, type AsyncZippable } from "fflate";

/**
 * Compress an IFC File into a .ifcZIP File in the browser using fflate.
 * If the file is already a .ifczip or .zip, it is returned unmodified.
 * Uses fflate asynchronous zip to prevent freezing the UI on large files.
 */
export async function compressIfcFile(file: File): Promise<File> {
  const lowerName = file.name.toLowerCase();
  if (lowerName.endsWith(".ifczip") || lowerName.endsWith(".zip")) {
    return file;
  }

  const arrayBuffer = await file.arrayBuffer();
  const u8data = new Uint8Array(arrayBuffer);

  const innerName = file.name;
  const zipName = file.name.replace(/\.ifc$/i, "") + ".ifczip";

  const zippable: AsyncZippable = {
    [innerName]: [u8data, { level: 6 }],
  };

  return new Promise<File>((resolve, reject) => {
    zip(zippable, (err, data) => {
      if (err) {
        return reject(err);
      }
      const blob = new Blob([data.buffer], { type: "application/zip" });
      const compressedFile = new File([blob], zipName, {
        type: "application/zip",
        lastModified: Date.now(),
      });
      resolve(compressedFile);
    });
  });
}

/**
 * Batch compress multiple files, returning the compressed files and statistics.
 */
export async function compressIfcFiles(
  files: File[],
  onStatus?: (current: number, total: number, fileName: string) => void,
): Promise<{ compressedFiles: File[]; totalOriginalBytes: number; totalCompressedBytes: number }> {
  let totalOriginalBytes = 0;
  let totalCompressedBytes = 0;
  const compressedFiles: File[] = [];

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    totalOriginalBytes += file.size;
    onStatus?.(i + 1, files.length, file.name);

    if (file.name.toLowerCase().endsWith(".ifc")) {
      const compressed = await compressIfcFile(file);
      totalCompressedBytes += compressed.size;
      compressedFiles.push(compressed);
    } else {
      totalCompressedBytes += file.size;
      compressedFiles.push(file);
    }
  }

  return { compressedFiles, totalOriginalBytes, totalCompressedBytes };
}
