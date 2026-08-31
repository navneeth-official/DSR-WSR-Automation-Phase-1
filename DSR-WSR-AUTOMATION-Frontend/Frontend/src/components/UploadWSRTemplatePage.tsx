import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Presentation, Upload } from "lucide-react";
import {
  fetchWsrTemplate,
  fetchWsrTemplatePreviewSlides,
  uploadWsrTemplate,
  type WsrPreviewSlide,
  type WsrTemplateInfo,
} from "@/api/wsr";
import { WSRPptViewer } from "@/components/WSRPptViewer";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatUploadedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function UploadWSRTemplatePage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [templateInfo, setTemplateInfo] = useState<WsrTemplateInfo | null>(null);
  const [previewSlides, setPreviewSlides] = useState<WsrPreviewSlide[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const loadExistingTemplate = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const info = await fetchWsrTemplate();
      setTemplateInfo(info);
      if (info) {
        const slides = await fetchWsrTemplatePreviewSlides();
        setPreviewSlides(slides);
      } else {
        setPreviewSlides([]);
      }
    } catch (err) {
      setTemplateInfo(null);
      setPreviewSlides([]);
      setError(err instanceof Error ? err.message : "Failed to load template");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadExistingTemplate();
  }, [loadExistingTemplate]);

  const handleFileSelected = async (file: File | undefined) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pptx")) {
      setError("Please upload a .pptx file.");
      return;
    }

    setUploading(true);
    setError("");
    try {
      const result = await uploadWsrTemplate(file);
      setTemplateInfo(result);
      setPreviewSlides(result.preview_slides);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 bg-gray-50">
      <div className="px-6 py-4 bg-white border-b border-gray-200 flex-shrink-0">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-gray-800">Upload WSR Template</h2>
            <p className="text-xs text-gray-400 mt-0.5 max-w-2xl">
              Upload a reference template for preview and storage. WSR deck generation always
              uses the built-in H-E-B G10X master template in the codebase.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
              className="hidden"
              onChange={(e) => void handleFileSelected(e.target.files?.[0])}
            />
            <button
              type="button"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-2 px-4 py-2 bg-brand-orange text-white rounded-lg text-sm font-medium hover:bg-brand-orange-hover disabled:opacity-60"
            >
              {uploading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Upload className="w-4 h-4" />
              )}
              {uploading ? "Uploading…" : "Upload template"}
            </button>
          </div>
        </div>

        {templateInfo && (
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
            <span>
              File: <span className="font-medium text-gray-700">{templateInfo.original_filename}</span>
            </span>
            <span>Slides: {templateInfo.slide_count}</span>
            <span>Size: {formatBytes(templateInfo.file_size_bytes)}</span>
            <span>Uploaded: {formatUploadedAt(templateInfo.uploaded_at)}</span>
          </div>
        )}

        {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
      </div>

      <div className="flex-1 min-h-0 flex items-stretch justify-center p-6">
        {loading ? (
          <div className="flex flex-col items-center justify-center text-center">
            <Loader2 className="w-8 h-8 text-brand-red animate-spin mb-3" />
            <p className="text-sm text-gray-600">Loading template preview…</p>
          </div>
        ) : previewSlides.length > 0 && templateInfo ? (
          <div className="w-full max-w-6xl min-h-0 bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <WSRPptViewer
              previewSlides={previewSlides}
              filename={templateInfo.original_filename}
              showSlideThumbnails={false}
            />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-center max-w-md px-6 py-16 bg-white border border-dashed border-gray-300 rounded-2xl shadow-sm">
            <Presentation className="w-12 h-12 text-gray-300 mb-4" />
            <p className="text-sm font-semibold text-gray-700">No template uploaded yet</p>
            <p className="text-xs text-gray-400 mt-2 leading-relaxed">
              Upload a `.pptx` template to preview it here. The file will be stored under
              `backend/Jira-Automation/output/` as `WSR_UPLOADED_TEMPLATE.pptx`.
            </p>
            <button
              type="button"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
              className="mt-5 inline-flex items-center gap-2 px-4 py-2 border border-brand-red/30 text-brand-red rounded-lg text-sm font-medium hover:bg-brand-red/10 disabled:opacity-60"
            >
              <Upload className="w-4 h-4" />
              Choose template file
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
