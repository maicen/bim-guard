import { zipSync, type Zippable } from "fflate";

self.onmessage = async (e: MessageEvent) => {
  try {
    const { fileName, u8data, fileType } = e.data;
    
    const zipName = fileName.replace(/\.ifc$/i, "") + ".ifczip";
    
    const zippable: Zippable = {
      [fileName]: [u8data, { level: 6 }],
    };
    
    // Perform synchronous zip in the worker thread (does not block main thread)
    const data = zipSync(zippable);
    
    // Transfer the ArrayBuffer back to avoid memory duplication
    (self as any).postMessage({ success: true, data, zipName, originalType: fileType }, [data.buffer]);
  } catch (err: any) {
    (self as any).postMessage({ success: false, error: err.message });
  }
};
