import api from "./api";

export async function uploadFiles(files: File[]) {

    console.log("========== UPLOAD REQUEST ==========");

    const formData = new FormData();

    files.forEach((file) => {
        formData.append("files", file);
    });

    console.time("UPLOAD");

    try {

        const response = await api.post(
            "/upload/files",
            formData,
            {
                headers: {
                    "Content-Type": "multipart/form-data",
                },
            },
        );

        console.timeEnd("UPLOAD");
        console.log("UPLOAD RESPONSE", response);

        return response.data;

    } catch (err) {

        console.timeEnd("UPLOAD");
        throw err;

    }

}