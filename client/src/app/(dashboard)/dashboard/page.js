import { OverviewView } from "@/components/domain/overview-view";

export const metadata = { title: "Overview" };

export default function DashboardPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <OverviewView />
    </div>
  );
}
