import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { Account } from "./types";

export function useAAAccounts() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedEmail, setSelectedEmail] = useState("");
  const [balance, setBalance] = useState<string | null>(null);
  const [sessionError, setSessionError] = useState("");

  useEffect(() => {
    api.getAccounts("ARTIFICIALANALYSIS").then((accs) => {
      const withSession = accs.filter((a) => a.session_state && !a.disabled);
      setAccounts(withSession);
      if (withSession.length > 0) setSelectedEmail(withSession[0].email);
    });
  }, []);

  useEffect(() => {
    if (!selectedEmail) return;
    setBalance(null);
    setSessionError("");
    api
      .aaGetSession(selectedEmail)
      .then((s) => setBalance(s.org.balance))
      .catch((e) => setSessionError(String(e)));
  }, [selectedEmail]);

  return { accounts, selectedEmail, setSelectedEmail, balance, sessionError };
}
