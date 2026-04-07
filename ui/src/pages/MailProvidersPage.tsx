import { useState } from "react";
import MailProviderTable from "../components/MailProviderTable";
import ProviderKeyTable from "../components/ProviderKeyTable";

const TABS = [
  {
    id: "mail-providers",
    label: "Mail Providers",
    icon: (
      <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
        <path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z" />
        <path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z" />
      </svg>
    ),
  },
  {
    id: "provider-keys",
    label: "Provider Keys",
    icon: (
      <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M18 8a6 6 0 01-7.743 5.743L10 14l-1 1-1 1H6v2H2v-4l4.257-4.257A6 6 0 1118 8zm-6-4a1 1 0 100 2 2 2 0 012 2 1 1 0 102 0 4 4 0 00-4-4z" clipRule="evenodd" />
      </svg>
    ),
  },
];

export default function MailProvidersPage() {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <div className="w-full h-full flex flex-col">
      {/* Tab header */}
      <div className="flex items-center gap-1 mb-6 bg-gray-100/70 rounded-xl p-1 w-fit">
        {TABS.map((tab, i) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(i)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === i
                ? "bg-white text-brand-700 shadow-sm border border-gray-200/80"
                : "text-gray-500 hover:text-gray-700 hover:bg-white/60"
            }`}
          >
            <span className={activeTab === i ? "text-brand-600" : "text-gray-400"}>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0">
        {activeTab === 0 && <MailProviderTable />}
        {activeTab === 1 && <ProviderKeyTable />}
      </div>
    </div>
  );
}
