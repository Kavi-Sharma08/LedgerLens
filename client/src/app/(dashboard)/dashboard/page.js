import { OverviewView } from "@/components/domain/overview-view";

export const metadata = { title: "Overview" };

function greetingFor(hour) {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage() {
  const greeting = greetingFor(new Date().getHours());
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <OverviewView greeting={greeting} />
    </div>
  );
}
