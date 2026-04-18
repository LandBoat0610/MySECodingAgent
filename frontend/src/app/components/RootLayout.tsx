import { Outlet, Link, useLocation } from "react-router";
import { Code2, BarChart3 } from "lucide-react";

export function RootLayout() {
  const location = useLocation();

  return (
    <div className="h-screen w-screen bg-[#0D1117] text-gray-100 flex flex-col">
      {/* Header Navigation */}
      <header className="h-14 border-b border-gray-800 bg-[#161B22] flex items-center px-6">
        <div className="flex items-center gap-3 mr-8">
          <Code2 className="w-6 h-6 text-blue-400" />
          <span className="text-lg font-semibold">CodeClaw</span>
        </div>

        <nav className="flex gap-1">
          <Link
            to="/"
            className={`px-4 py-2 rounded-md transition-colors ${
              location.pathname === "/"
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
            }`}
          >
            <div className="flex items-center gap-2">
              <Code2 className="w-4 h-4" />
              IDE
            </div>
          </Link>
          <Link
            to="/dashboard"
            className={`px-4 py-2 rounded-md transition-colors ${
              location.pathname === "/dashboard"
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
            }`}
          >
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Dashboard
            </div>
          </Link>
        </nav>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
