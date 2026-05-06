import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import App from "./app/App";
import UploadPage from "./pages/UploadPage";
import BatchPage from "./pages/BatchPage";
import ReviewPage from "./pages/ReviewPage";
import ExportPage from "./pages/ExportPage";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <App>
        <Routes>
          <Route path="/" element={<Navigate to="/upload" replace />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/batches/:batchId" element={<BatchPage />} />
          <Route path="/pages/:pageId/review" element={<ReviewPage />} />
          <Route path="/batches/:batchId/export" element={<ExportPage />} />
        </Routes>
      </App>
    </BrowserRouter>
  </React.StrictMode>,
);
