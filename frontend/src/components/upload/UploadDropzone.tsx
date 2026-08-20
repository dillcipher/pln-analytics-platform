import type {
  ChangeEvent,
  Dispatch,
  SetStateAction,
} from "react";

type Props = {
  files: File[];
  setFiles: Dispatch<SetStateAction<File[]>>;
};

export default function UploadDropzone({
  files,
  setFiles,
}: Props) {
  function handleChange(
    e: ChangeEvent<HTMLInputElement>
  ) {
    if (!e.target.files) return;

    setFiles(Array.from(e.target.files));
  }

  return (
    <div
      style={{
        border: "2px dashed #2d4f70",
        borderRadius: 12,
        padding: 40,
        textAlign: "center",
        background: "#121826",
      }}
    >
      <h2>Upload PLN Dataset</h2>

      <input
        type="file"
        multiple
        accept=".xlsx,.xls"
        onChange={handleChange}
      />

      <p>Excel (.xlsx, .xls)</p>

      <p>{files.length} file selected</p>
    </div>
  );
}