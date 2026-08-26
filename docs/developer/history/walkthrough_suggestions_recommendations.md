# Walkthrough: AI Suggestions & Recommendation Engine

We have designed, built, and verified the rule-based **Recommendation Engine** and the **AI Suggestions Pane** in Power Mode using the SQLite-backed persistent model.

## Implementation Details

1. **Declarative Rule Engine**:
   * Created [`recommendation.py`](../../../cyguide/engine/recommendation.py) with four declarative recommendation rules:
     * `WebServiceRecommendationRule`: Suggests `gobuster` directory scanning for services running on HTTP/HTTPS ports (80, 443, 8080).
     * `WebVulnerabilityRecommendationRule`: Suggests `nikto` vulnerability scanning for confirmed web endpoints.
     * `SubdomainRecommendationRule`: Suggests `subfinder` subdomain discovery for targets with hostnames/domains.
     * `WhoisRecommendationRule`: Suggests `whois` lookup for hosts with public IP addresses.
   * Leveraged the Pydantic `.status = "proposed"` property to prevent cascading loop recursion during upsert.

2. **Integration & Lifecycle Wiring**:
   * Initialized and registered the engine on startup in [`app.py`](../../../cyguide/app.py).
   * Implemented `get_proposed_findings` and `dismiss_proposed_finding` in [`power_facade.py`](../../../cyguide/engine/power_facade.py) to read and delete suggestions dynamically without altering the frozen Tier 1 database schema.

3. **UI Integration (TUI)**:
   * Created the [`SuggestionsPane` widget](../../../cyguide/ui/widgets/power.py) to display recommendations dynamically (`💡 [tool] ❯ [target]`).
   * Integrated the pane into the sidebar layout of [`PowerModeScreen`](../../../cyguide/ui/screens/power.py) and wired Approved/Dismissed keyboard controls:
     * **`Enter` or Click (Approve)**: Pre-populates the command prompt input box with the recommended command and focuses it, allowing the operator to review, edit, or press Enter to run.
     * **`d` / `x` / `delete` (Dismiss)**: Deletes the recommendation from SQLite.
   * Adjusted layout heights and added styles in [`style.css`](../../../cyguide/ui/style.css).

---
