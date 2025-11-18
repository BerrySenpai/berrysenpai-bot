const express = require("express");
const { execFile } = require("child_process");
const cors = require("cors");

const app = express();
app.use(cors());

app.get("/api/extract", (req, res) => {
  const url = req.query.url;
  if (!url) return res.json({ error: "url required" });

  execFile("yt-dlp", ["-J", url], (err, stdout) => {
    if (err) return res.json({ error: err.message });

    try {
      const info = JSON.parse(stdout);

      const streams = (info.formats || []).map((f) => ({
        quality: f.format_note || f.resolution || "unknown",
        type: f.vcodec ? "video" : "audio",
        ext: f.ext,
        filesize: f.filesize || f.filesize_approx || "",
        url: f.url,
      }));

      res.json({
        title: info.title,
        thumbnails: (info.thumbnails || []).map((t) => t.url),
        streams,
      });
    } catch {
      res.json({ error: "parse error" });
    }
  });
});

app.listen(3000, () => console.log("API RUNNING on port 3000"));
