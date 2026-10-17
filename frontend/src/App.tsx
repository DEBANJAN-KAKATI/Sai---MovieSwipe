import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { App as CapApp } from "@capacitor/app";
import { isNative } from "./api/base";
import { api } from "./api/client";
import { BottomNav, SideNav } from "./components/BottomNav";
import { Toasts } from "./components/Toasts";
import { Discover } from "./pages/Discover";
import { Landing } from "./pages/Landing";
import { Lists } from "./pages/Lists";
import { Onboarding, Welcome } from "./pages/Onboarding";
import { PartyPage } from "./pages/Party";
import { Profile } from "./pages/Profile";
import { FriendCompare, PublicList, SharedList, Social } from "./pages/Social";
import { JoinRedirect, SessionRoom, Together } from "./pages/Together";
import { useAuth } from "./store";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 15_000, refetchOnWindowFocus: false, retry: 1 } },
});

/** Android back button: close an open sheet first, then go back, then leave the app. */
function useNativeBackButton() {
  useEffect(() => {
    if (!isNative) return;
    const handle = CapApp.addListener("backButton", ({ canGoBack }) => {
      if (document.querySelector(".sheet-backdrop")) {
        window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
      } else if (canGoBack && location.pathname !== "/") {
        window.history.back();
      } else {
        CapApp.exitApp();
      }
    });
    return () => {
      handle.then((h) => h.remove());
    };
  }, []);
}

/** Invite links work before onboarding so a friend can jump straight into a session. */
const SKIP_ONBOARDING = /^\/(join|party|session)\//;

function AuthedApp() {
  const token = useAuth((s) => s.token);
  const user = useAuth((s) => s.user);
  const setUser = useAuth((s) => s.setUser);
  const location = useLocation();
  const me = useQuery({ queryKey: ["me", token], queryFn: api.me, enabled: !!token });

  useEffect(() => {
    if (me.data) setUser(me.data);
  }, [me.data, setUser]);

  // Website visitors get the landing page; the Android app keeps its compact welcome screen.
  if (!token) return isNative ? <Welcome /> : <Landing />;
  if (!user) return null;
  if (!user.onboarded && !SKIP_ONBOARDING.test(location.pathname)) {
    return <Onboarding onDone={() => queryClient.invalidateQueries()} />;
  }

  return (
    <div className="layout">
      <SideNav />
      <main className="shell">
      <Routes>
        <Route path="/" element={<Discover />} />
        <Route path="/lists" element={<Lists />} />
        <Route path="/together" element={<Together />} />
        <Route path="/session/:id" element={<SessionRoom />} />
        <Route path="/join/:code" element={<JoinRedirect />} />
        <Route path="/social" element={<Social />} />
        <Route path="/friends/:id" element={<FriendCompare />} />
        <Route path="/shared/:id" element={<SharedList />} />
        <Route path="/party/:code" element={<PartyPage />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </main>
      <BottomNav />
    </div>
  );
}

export default function App() {
  useNativeBackButton();
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/l/:id" element={<PublicList />} />
          <Route path="*" element={<AuthedApp />} />
        </Routes>
        <Toasts />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
