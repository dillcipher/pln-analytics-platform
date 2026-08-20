type Props = {
  files: File[];
};

export default function UploadFileTable({
  files,
}: Props) {

  return (

    <table
      style={{
        width: "100%",
        marginTop: 20,
      }}
    >

      <thead>

        <tr>

          <th>Name</th>

          <th>Size (KB)</th>

        </tr>

      </thead>

      <tbody>

        {files.map((file) => (

          <tr key={file.name}>

            <td>{file.name}</td>

            <td>
              {(file.size / 1024).toFixed(2)}
            </td>

          </tr>

        ))}

      </tbody>

    </table>

  );

}