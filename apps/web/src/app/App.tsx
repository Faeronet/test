import { Link } from "react-router-dom";
import type { PropsWithChildren } from "react";

export default function App({ children }: PropsWithChildren) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>drawing2dxf</h1>
        <nav>
          <Link to="/upload">Upload</Link>
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}
