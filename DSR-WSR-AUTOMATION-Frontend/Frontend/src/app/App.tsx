import { useState, useCallback, useRef, useEffect, useMemo, Fragment } from "react";
import { catalogToImportedTracks, fetchTeamTracks, isViewDsrSidebarTrack, type TrackListItem } from "@/api/dsr";
import {
  addStoryComment,
  apiStoryToRecord,
  createStory,
  dedupeLatestRecords,
  fetchAllStories,
  fetchStoriesByAssignee,
  fetchStoriesBySprint,
  fetchDsrStoriesByTrack,
  fetchStoriesByTrack,
  importStories,
  recordToSavePayload,
  regenerateStoryTitle,
  storiesToLatestRecords,
  storiesToRecords,
  storyRowKey,
  todayIsoDate,
  updateStory,
  type JiraStoryRecord,
} from "@/api/stories";
import { RovoRequestSidebar } from "@/components/intake/RovoRequestSidebar";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { WSRReportPanel } from "@/components/WSRReportPanel";
import { WSRTemplateSelector } from "@/components/WSRTemplateSelector";
import { ViewWSRPage } from "@/components/ViewWSRPage";
import { StoryHistoryModal } from "@/components/StoryHistoryModal";
import { StoryCommentModal } from "@/components/StoryCommentModal";
import {
  Upload,
  Ticket,
  ChevronDown,
  Search,
  Plus,
  Trash2,
  Download,
  X,
  Filter,
  SlidersHorizontal,
  Calendar,
  CheckCircle2,
  Circle,
  AlertCircle,
  Bug,
  BookOpen,
  Zap,
  ClipboardList,
  Sparkles,
  MessageCircle,
} from "lucide-react";

const SAMPLE_DATA = [
  // ── Locations (LOC) ──────────────────────────────────────────────
  { project_key: "LOC", project_name: "Location Core Service", sprint_name: "Q2.14 FY26 Fornax", sprint_start_date: "2026-04-30", sprint_end_date: "2026-05-14", jira_key: "LOC-2750", summary: "FAM | MFR | Offsite Warehouse List sorted by Offsite Number instead of creation date", description: "The table should be sorted by record creation date, but is sorted by offsite number", issue_type: "Bug", priority: "Low", assignee: "Vineed Kaladharan", reporter: "Vinu Lilitha", status: "Done", story_points: null, created_date: "2026-05-11", updated_date: "2026-05-11", resolved_date: "2026-05-11", snapshot_date: "2026-06-11" },
  { project_key: "LOC", project_name: "Location Core Service", sprint_name: "Q2.14 FY26 Fornax", sprint_start_date: "2026-04-30", sprint_end_date: "2026-05-14", jira_key: "LOC-2749", summary: "FAM | MFR | Status Column Displays X for Offsite Warehouses with New status", description: "The Status column shows X when the offsite warehouse status is New – Under Construction", issue_type: "Bug", priority: "Low", assignee: "Vineed Kaladharan", reporter: "Vinu Lilitha", status: "Done", story_points: null, created_date: "2026-05-11", updated_date: "2026-05-11", resolved_date: "2026-05-11", snapshot_date: "2026-06-11" },
  { project_key: "LOC", project_name: "Location Core Service", sprint_name: "Q2.14 FY26 Fornax", sprint_start_date: "2026-04-30", sprint_end_date: "2026-05-14", jira_key: "LOC-2744", summary: "FAM | MFR | Changes to Offsite Warehouse - Create & Update (R)", description: "Incorporate acceptance criteria changes for Offsite Warehouse Create and Edit pages", issue_type: "Story", priority: "Low", assignee: "Vineed Kaladharan", reporter: "Suraj Seshadri", status: "Done", story_points: 1, created_date: "2026-05-07", updated_date: "2026-05-11", resolved_date: "2026-05-11", snapshot_date: "2026-06-11" },
  { project_key: "LOC", project_name: "Location Core Service", sprint_name: "Q2.14 FY26 Fornax", sprint_start_date: "2026-04-30", sprint_end_date: "2026-05-14", jira_key: "LOC-2742", summary: "FAM | MFR | Validation issues: warehouse number length and tobacco permit flag", description: "Min length for Number field should be 3 digits; tobacco permit field should be non-mandatory", issue_type: "Bug", priority: "Low", assignee: "Vineed Kaladharan", reporter: "Vinu Lilitha", status: "Done", story_points: null, created_date: "2026-05-06", updated_date: "2026-05-11", resolved_date: "2026-05-11", snapshot_date: "2026-06-11" },
  { project_key: "LOC", project_name: "Location Core Service", sprint_name: "Q2.14 FY26 Fornax", sprint_start_date: "2026-04-30", sprint_end_date: "2026-05-14", jira_key: "LOC-2660", summary: "FAM | MFR | Warehouse - Edit Offsite Warehouses - Save FAM-API (R)", description: "As a Partner, when I edit an offsite warehouse, I want to save the information to JavaDAO", issue_type: "Story", priority: "Low", assignee: "Vignesh Krishnan", reporter: "Sreejith Keeriyadathu Kalarikkal", status: "Done", story_points: 3, created_date: "2026-03-30", updated_date: "2026-05-04", resolved_date: "2026-05-04", snapshot_date: "2026-06-11" },
  { project_key: "LOC", project_name: "Location Core Service", sprint_name: "Q2.14 FY26 Fornax", sprint_start_date: "2026-04-30", sprint_end_date: "2026-05-14", jira_key: "LOC-2659", summary: "FAM | MFR | Warehouse - Create Offsite Warehouse - Save FAM-API (R)", description: "As a Partner, when I create a new Offsite Warehouse, I want to save the information to EMD", issue_type: "Story", priority: "Low", assignee: "Vignesh Krishnan", reporter: "Sreejith Keeriyadathu Kalarikkal", status: "Done", story_points: 3, created_date: "2026-03-30", updated_date: "2026-05-04", resolved_date: "2026-05-04", snapshot_date: "2026-06-11" },
  { project_key: "LOC", project_name: "Location Core Service", sprint_name: "Q2.13FY26 Eridanus", sprint_start_date: "2026-04-16", sprint_end_date: "2026-04-30", jira_key: "LOC-2367", summary: "FAM | MFR | Warehouse - Edit Warehouse - UI (R)", description: "As a Partner, I would like an update functionality on the warehouse view screen", issue_type: "Story", priority: "Low", assignee: "Vineed Kaladharan", reporter: "Sreejith Keeriyadathu Kalarikkal", status: "Done", story_points: 3, created_date: "2026-01-20", updated_date: "2026-05-06", resolved_date: "2026-04-24", snapshot_date: "2026-06-11" },
  { project_key: "LOC", project_name: "Location Core Service", sprint_name: "Q2.13FY26 Eridanus", sprint_start_date: "2026-04-16", sprint_end_date: "2026-04-30", jira_key: "LOC-2362", summary: "FAM | MFR | Warehouse - Create Warehouse - UI (R)", description: "As a Partner, I want a warehouse creation UI screen to input required information", issue_type: "Story", priority: "Low", assignee: "Vineed Kaladharan", reporter: "Sreejith Keeriyadathu Kalarikkal", status: "Done", story_points: 3, created_date: "2026-01-20", updated_date: "2026-05-06", resolved_date: "2026-04-24", snapshot_date: "2026-06-11" },
  { project_key: "LOC", project_name: "Location Core Service", sprint_name: "Q2.13FY26 Eridanus", sprint_start_date: "2026-04-16", sprint_end_date: "2026-04-30", jira_key: "LOC-2357", summary: "FAM | Mainframe Retirement | Warehouse - List Page | UI (R)", description: "As a user with warehouse management permissions, I want to see all main warehouses in a list", issue_type: "Story", priority: "Low", assignee: "Vineed Kaladharan", reporter: "Sreejith Keeriyadathu Kalarikkal", status: "Done", story_points: 3, created_date: "2026-01-20", updated_date: "2026-05-11", resolved_date: "2026-04-21", snapshot_date: "2026-06-11" },

  // ── Cost (COST) ───────────────────────────────────────────────────
  { project_key: "COST", project_name: "Cost Core Service", sprint_name: "Nacogdoches - 248", sprint_start_date: "2026-03-18", sprint_end_date: "2026-04-01", jira_key: "COST-5385", summary: "Replay CST_ELEM Messages to Capture all Buyer Adjustment (meat) Records", description: "Based on research in COST-5382, capture all buyer adjustment records for all related item class codes", issue_type: "Story", priority: "Low", assignee: "Rishi Manoj", reporter: "Danny Baggett", status: "Done", story_points: 1, created_date: "2026-03-05", updated_date: "2026-05-04", resolved_date: "2026-03-24", snapshot_date: "2026-06-11" },
  { project_key: "COST", project_name: "Cost Core Service", sprint_name: "Nacogdoches - 248", sprint_start_date: "2026-03-18", sprint_end_date: "2026-04-01", jira_key: "COST-5403", summary: "Expose multiple-item DSD ledger endpoint for downstream consumers", description: "Add a new endpoint that accepts multiple item IDs and returns DSD ledger entries in bulk", issue_type: "Story", priority: "Low", assignee: "Rishi Manoj", reporter: "Danny Baggett", status: "Done", story_points: 2, created_date: "2026-03-10", updated_date: "2026-04-01", resolved_date: "2026-04-01", snapshot_date: "2026-06-11" },
  { project_key: "COST", project_name: "Cost Core Service", sprint_name: "Sulphur Springs - 249", sprint_start_date: "2026-05-27", sprint_end_date: "2026-06-09", jira_key: "COST-5406", summary: "Finalize cash discount logic for DSD cost calculation", description: "Update cost calculation engine to correctly apply cash discount tiers from vendor agreements", issue_type: "Story", priority: "Medium", assignee: "Rishi Manoj", reporter: "Danny Baggett", status: "In Progress", story_points: 3, created_date: "2026-05-20", updated_date: "2026-06-05", resolved_date: null, snapshot_date: "2026-06-11" },
  { project_key: "COST", project_name: "Cost Core Service", sprint_name: "Sulphur Springs - 249", sprint_start_date: "2026-05-27", sprint_end_date: "2026-06-09", jira_key: "COST-5411", summary: "Investigate timeout on /v1/active-ledgers-by-date/dsd endpoint", description: "Production support request: endpoint times out under high load during daily batch window", issue_type: "Task", priority: "High", assignee: "Danny Baggett", reporter: "Rishi Manoj", status: "In Progress", story_points: null, created_date: "2026-06-02", updated_date: "2026-06-10", resolved_date: null, snapshot_date: "2026-06-11" },

  // ── Pricing (PRC) ─────────────────────────────────────────────────
  { project_key: "PRC", project_name: "Pricing Core Service", sprint_name: "PRC Sprint 18", sprint_start_date: "2026-05-14", sprint_end_date: "2026-05-28", jira_key: "PRC-1120", summary: "Dynamic pricing engine integration with cost feed", description: "Integrate the pricing engine with the real-time cost feed to enable cost-based pricing rules", issue_type: "Story", priority: "Medium", assignee: "Ananya Mehta", reporter: "Kevin Loh", status: "Done", story_points: 5, created_date: "2026-05-01", updated_date: "2026-05-28", resolved_date: "2026-05-28", snapshot_date: "2026-06-11" },
  { project_key: "PRC", project_name: "Pricing Core Service", sprint_name: "PRC Sprint 18", sprint_start_date: "2026-05-14", sprint_end_date: "2026-05-28", jira_key: "PRC-1122", summary: "Fix rounding issue in promotional price calculation", description: "Promotional prices round up to the nearest cent in some edge cases causing overcharge", issue_type: "Bug", priority: "Medium", assignee: "Ananya Mehta", reporter: "Kevin Loh", status: "Done", story_points: 1, created_date: "2026-05-10", updated_date: "2026-05-25", resolved_date: "2026-05-25", snapshot_date: "2026-06-11" },
  { project_key: "PRC", project_name: "Pricing Core Service", sprint_name: "PRC Sprint 18", sprint_start_date: "2026-05-14", sprint_end_date: "2026-05-28", jira_key: "PRC-1123", summary: "Price ladder configuration portal V2 for store managers", description: "Build a self-service UI for store managers to configure and preview price ladder tiers", issue_type: "Story", priority: "Medium", assignee: "Kevin Loh", reporter: "Ananya Mehta", status: "In Progress", story_points: 5, created_date: "2026-05-05", updated_date: "2026-06-01", resolved_date: null, snapshot_date: "2026-06-11" },
  { project_key: "PRC", project_name: "Pricing Core Service", sprint_name: "PRC Sprint 19", sprint_start_date: "2026-06-02", sprint_end_date: "2026-06-16", jira_key: "PRC-1130", summary: "Competitor price feed ingestion pipeline", description: "Build an ingestion pipeline to consume competitor price feeds and normalize them for comparison", issue_type: "Story", priority: "Low", assignee: "Ananya Mehta", reporter: "Kevin Loh", status: "In Progress", story_points: 3, created_date: "2026-05-28", updated_date: "2026-06-10", resolved_date: null, snapshot_date: "2026-06-11" },

  // ── SPUR ──────────────────────────────────────────────────────────
  { project_key: "SPUR", project_name: "Supplier Core Service – SPUR", sprint_name: "SPUR Sprint 22", sprint_start_date: "2026-04-16", sprint_end_date: "2026-04-30", jira_key: "SPUR-441", summary: "Supplier unit reconciliation batch job scheduling refactor", description: "Refactor the scheduling layer to support configurable cron expressions per client", issue_type: "Story", priority: "Low", assignee: "Priya Nambiar", reporter: "Tom Alves", status: "Done", story_points: 3, created_date: "2026-04-05", updated_date: "2026-04-30", resolved_date: "2026-04-30", snapshot_date: "2026-06-11" },
  { project_key: "SPUR", project_name: "Supplier Core Service – SPUR", sprint_name: "SPUR Sprint 22", sprint_start_date: "2026-04-16", sprint_end_date: "2026-04-30", jira_key: "SPUR-442", summary: "Unit of measure conversion table migration to new schema", description: "Migrate UOM conversion data from legacy schema to the new normalised schema", issue_type: "Story", priority: "Low", assignee: "Priya Nambiar", reporter: "Tom Alves", status: "Done", story_points: 2, created_date: "2026-04-06", updated_date: "2026-04-28", resolved_date: "2026-04-28", snapshot_date: "2026-06-11" },
  { project_key: "SPUR", project_name: "Supplier Core Service – SPUR", sprint_name: "SPUR Sprint 23", sprint_start_date: "2026-05-01", sprint_end_date: "2026-05-15", jira_key: "SPUR-443", summary: "Fix null pointer in SPUR event consumer on empty payload", description: "Consumer throws NullPointerException when event payload has an empty items array", issue_type: "Bug", priority: "High", assignee: "Tom Alves", reporter: "Priya Nambiar", status: "In Progress", story_points: 1, created_date: "2026-04-28", updated_date: "2026-05-10", resolved_date: null, snapshot_date: "2026-06-11" },
  { project_key: "SPUR", project_name: "Supplier Core Service – SPUR", sprint_name: "SPUR Sprint 23", sprint_start_date: "2026-05-01", sprint_end_date: "2026-05-15", jira_key: "SPUR-444", summary: "QA automation suite for supplier unit reconciliation", description: "Create end-to-end automated test suite covering happy path and error scenarios for SPUR", issue_type: "Task", priority: "Medium", assignee: "Tom Alves", reporter: "Priya Nambiar", status: "To Do", story_points: 3, created_date: "2026-05-01", updated_date: "2026-05-01", resolved_date: null, snapshot_date: "2026-06-11" },

  // ── Supplier (SUP) ────────────────────────────────────────────────
  { project_key: "SUP", project_name: "Supplier Core Service", sprint_name: "Sprint SUP-14", sprint_start_date: "2026-04-30", sprint_end_date: "2026-05-14", jira_key: "SUP-883", summary: "EDI 850 inbound purchase order parser upgrade to v4 spec", description: "Upgrade the EDI 850 parser to handle the v4 spec which adds new mandatory segments", issue_type: "Story", priority: "Medium", assignee: "Laura Chen", reporter: "Miguel Santos", status: "Done", story_points: 5, created_date: "2026-04-20", updated_date: "2026-05-14", resolved_date: "2026-05-14", snapshot_date: "2026-06-11" },
  { project_key: "SUP", project_name: "Supplier Core Service", sprint_name: "Sprint SUP-14", sprint_start_date: "2026-04-30", sprint_end_date: "2026-05-14", jira_key: "SUP-885", summary: "Fix ASN acknowledgement timeout not retrying on 503 responses", description: "When the downstream system returns 503, the ASN acknowledgement service does not retry", issue_type: "Bug", priority: "High", assignee: "Miguel Santos", reporter: "Laura Chen", status: "Done", story_points: 1, created_date: "2026-04-25", updated_date: "2026-05-10", resolved_date: "2026-05-10", snapshot_date: "2026-06-11" },
  { project_key: "SUP", project_name: "Supplier Core Service", sprint_name: "Sprint SUP-15", sprint_start_date: "2026-05-14", sprint_end_date: "2026-05-28", jira_key: "SUP-882", summary: "Supplier onboarding self-service portal V2 – document upload", description: "Add document upload capability to the supplier self-service portal for compliance docs", issue_type: "Story", priority: "Medium", assignee: "Laura Chen", reporter: "Miguel Santos", status: "In Progress", story_points: 8, created_date: "2026-05-01", updated_date: "2026-06-05", resolved_date: null, snapshot_date: "2026-06-11" },
  { project_key: "SUP", project_name: "Supplier Core Service", sprint_name: "Sprint SUP-15", sprint_start_date: "2026-05-14", sprint_end_date: "2026-05-28", jira_key: "SUP-886", summary: "Supplier catalog sync to pricing feed on item update", description: "When a supplier updates an item price in the catalog, automatically push the update to the pricing feed", issue_type: "Story", priority: "Low", assignee: "Miguel Santos", reporter: "Laura Chen", status: "To Do", story_points: 3, created_date: "2026-05-12", updated_date: "2026-05-12", resolved_date: null, snapshot_date: "2026-06-11" },

  // ── Wentforth (WNF) ───────────────────────────────────────────────
  { project_key: "WNF", project_name: "Wentforth", sprint_name: "WNF Sprint 9", sprint_start_date: "2026-04-16", sprint_end_date: "2026-04-30", jira_key: "WNF-201", summary: "Wentforth store profile sync with master data service", description: "Sync store profiles from master data service whenever attributes change", issue_type: "Story", priority: "Low", assignee: "Sara Kim", reporter: "James Park", status: "Done", story_points: 3, created_date: "2026-04-05", updated_date: "2026-04-30", resolved_date: "2026-04-30", snapshot_date: "2026-06-11" },
  { project_key: "WNF", project_name: "Wentforth", sprint_name: "WNF Sprint 9", sprint_start_date: "2026-04-16", sprint_end_date: "2026-04-30", jira_key: "WNF-202", summary: "Wentforth loyalty points redemption API integration", description: "Expose an API for POS systems to redeem loyalty points at checkout in real time", issue_type: "Story", priority: "Medium", assignee: "Sara Kim", reporter: "James Park", status: "Done", story_points: 5, created_date: "2026-04-06", updated_date: "2026-04-29", resolved_date: "2026-04-29", snapshot_date: "2026-06-11" },
  { project_key: "WNF", project_name: "Wentforth", sprint_name: "WNF Sprint 10", sprint_start_date: "2026-05-01", sprint_end_date: "2026-05-15", jira_key: "WNF-203", summary: "Fix loyalty expiry notification batch race condition", description: "Two worker threads can mark the same loyalty record as expired simultaneously causing duplicate emails", issue_type: "Bug", priority: "High", assignee: "James Park", reporter: "Sara Kim", status: "In Progress", story_points: 2, created_date: "2026-04-28", updated_date: "2026-05-08", resolved_date: null, snapshot_date: "2026-06-11" },
  { project_key: "WNF", project_name: "Wentforth", sprint_name: "WNF Sprint 10", sprint_start_date: "2026-05-01", sprint_end_date: "2026-05-15", jira_key: "WNF-204", summary: "Wentforth store configuration export utility", description: "Build a CLI utility to export store configuration as JSON for backup and migration purposes", issue_type: "Task", priority: "Low", assignee: "James Park", reporter: "Sara Kim", status: "To Do", story_points: 1, created_date: "2026-05-01", updated_date: "2026-05-01", resolved_date: null, snapshot_date: "2026-06-11" },

  // ── Pharmacy (PHRM) ───────────────────────────────────────────────
  { project_key: "PHRM", project_name: "Pharmacy and Wellness", sprint_name: "PHRM Sprint 11", sprint_start_date: "2026-04-30", sprint_end_date: "2026-05-14", jira_key: "PHRM-310", summary: "Prescription refill workflow redesign with patient-facing UI", description: "Redesign the refill workflow to be patient-initiated via the mobile app with real-time status updates", issue_type: "Story", priority: "Medium", assignee: "Dr. Aisha Patel", reporter: "Ben Okafor", status: "Done", story_points: 5, created_date: "2026-04-18", updated_date: "2026-05-14", resolved_date: "2026-05-14", snapshot_date: "2026-06-11" },
  { project_key: "PHRM", project_name: "Pharmacy and Wellness", sprint_name: "PHRM Sprint 11", sprint_start_date: "2026-04-30", sprint_end_date: "2026-05-14", jira_key: "PHRM-311", summary: "Controlled substance DEA number validation at point of sale", description: "Validate DEA registration numbers in real time before allowing controlled substance dispensing", issue_type: "Story", priority: "High", assignee: "Dr. Aisha Patel", reporter: "Ben Okafor", status: "Done", story_points: 3, created_date: "2026-04-20", updated_date: "2026-05-12", resolved_date: "2026-05-12", snapshot_date: "2026-06-11" },
  { project_key: "PHRM", project_name: "Pharmacy and Wellness", sprint_name: "PHRM Sprint 11", sprint_start_date: "2026-04-30", sprint_end_date: "2026-05-14", jira_key: "PHRM-313", summary: "Fix drug interaction alert false positives for common OTC combinations", description: "Alert engine incorrectly flags ibuprofen + acetaminophen as a dangerous interaction", issue_type: "Bug", priority: "Medium", assignee: "Ben Okafor", reporter: "Dr. Aisha Patel", status: "Done", story_points: 2, created_date: "2026-04-22", updated_date: "2026-05-09", resolved_date: "2026-05-09", snapshot_date: "2026-06-11" },
  { project_key: "PHRM", project_name: "Pharmacy and Wellness", sprint_name: "PHRM Sprint 12", sprint_start_date: "2026-05-14", sprint_end_date: "2026-05-28", jira_key: "PHRM-312", summary: "Insurance eligibility check real-time API via CoverMyMeds", description: "Integrate with CoverMyMeds API to verify patient insurance eligibility in under 2 seconds", issue_type: "Story", priority: "High", assignee: "Ben Okafor", reporter: "Dr. Aisha Patel", status: "In Progress", story_points: 5, created_date: "2026-05-01", updated_date: "2026-06-05", resolved_date: null, snapshot_date: "2026-06-11" },

  // ── GSS ────────────────────────────────────────────────────────────
  { project_key: "GSS", project_name: "Global Sourcing Solution", sprint_name: "GSS Sprint 7", sprint_start_date: "2026-04-16", sprint_end_date: "2026-04-30", jira_key: "GSS-155", summary: "Global store setup configuration export tool for onboarding", description: "Build a tool to export store setup configuration templates for new store onboarding workflows", issue_type: "Story", priority: "Low", assignee: "Carlos Rivera", reporter: "Fatima Al-Rashid", status: "Done", story_points: 3, created_date: "2026-04-05", updated_date: "2026-04-30", resolved_date: "2026-04-30", snapshot_date: "2026-06-11" },
  { project_key: "GSS", project_name: "Global Sourcing Solution", sprint_name: "GSS Sprint 7", sprint_start_date: "2026-04-16", sprint_end_date: "2026-04-30", jira_key: "GSS-158", summary: "GSS audit trail enhancement for configuration changes", description: "Record who changed what and when for all store configuration changes with a diff view", issue_type: "Story", priority: "Low", assignee: "Fatima Al-Rashid", reporter: "Carlos Rivera", status: "Done", story_points: 2, created_date: "2026-04-07", updated_date: "2026-04-29", resolved_date: "2026-04-29", snapshot_date: "2026-06-11" },
  { project_key: "GSS", project_name: "Global Sourcing Solution", sprint_name: "GSS Sprint 7", sprint_start_date: "2026-04-16", sprint_end_date: "2026-04-30", jira_key: "GSS-157", summary: "Fix store timezone mismatch in schedule export report", description: "Schedule export shows times in UTC instead of the store local timezone, causing confusion", issue_type: "Bug", priority: "Medium", assignee: "Fatima Al-Rashid", reporter: "Carlos Rivera", status: "Done", story_points: 1, created_date: "2026-04-10", updated_date: "2026-04-26", resolved_date: "2026-04-26", snapshot_date: "2026-06-11" },
  { project_key: "GSS", project_name: "Global Sourcing Solution", sprint_name: "GSS Sprint 8", sprint_start_date: "2026-05-01", sprint_end_date: "2026-05-15", jira_key: "GSS-156", summary: "Multi-region store attribute inheritance engine", description: "Implement a rules engine that allows regional default attributes to cascade to store-level overrides", issue_type: "Story", priority: "High", assignee: "Carlos Rivera", reporter: "Fatima Al-Rashid", status: "In Progress", story_points: 8, created_date: "2026-04-20", updated_date: "2026-06-08", resolved_date: null, snapshot_date: "2026-06-11" },
];

type JiraIssue = (typeof SAMPLE_DATA)[0] & { reportee?: string; date_assigned?: string };

type StoryStatus = "To Do" | "In Progress" | "Done";

function normalizeStatus(status: string | undefined | null): StoryStatus {
  const s = (status ?? "").trim().toLowerCase();
  if (s === "done" || s === "closed" || s === "resolved" || s === "complete" || s === "completed") return "Done";
  if (s === "in progress" || s === "inprogress" || s === "wip" || s === "active") return "In Progress";
  return "To Do";
}

function parseIsoDate(s: string): Date | null {
  if (!s?.trim()) return null;
  const d = new Date(s.includes("T") ? s.trim() : `${s.trim()}T12:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

function getDateAssigned(row: JiraIssue): string {
  return row.date_assigned?.trim() || row.created_date?.trim() || "";
}

function formatAssignedDate(row: JiraIssue): string {
  const raw = getDateAssigned(row);
  const d = parseIsoDate(raw);
  if (!d) return raw || "—";
  return fmtDateShort(d);
}

function formatSnapshotDate(row: JiraStoryRecord): string {
  const raw = row.snapshot_date?.trim() || "";
  const d = parseIsoDate(raw);
  if (!d) return raw || "—";
  return fmtDateShort(d);
}

function sortStoryVersions(rows: JiraStoryRecord[]): JiraStoryRecord[] {
  return [...rows].sort((a, b) => {
    const keyCmp = a.jira_key.localeCompare(b.jira_key);
    if (keyCmp !== 0) return keyCmp;
    const aSnap = Date.parse((a.snapshot_date || "").slice(0, 10)) || 0;
    const bSnap = Date.parse((b.snapshot_date || "").slice(0, 10)) || 0;
    return bSnap - aSnap;
  });
}

function filterRowsForSprintWeek(rows: JiraIssue[], sprintName: string): JiraIssue[] {
  const inSprint = rows.filter((r) => r.sprint_name === sprintName);
  if (inSprint.length === 0) return [];
  const starts = inSprint.map((r) => r.sprint_start_date).filter(Boolean) as string[];
  const ends = inSprint.map((r) => r.sprint_end_date).filter(Boolean) as string[];
  if (!starts.length || !ends.length) return inSprint;
  const minStart = starts.reduce((a, b) => {
    const da = parseIsoDate(a);
    const db = parseIsoDate(b);
    if (!da) return b;
    if (!db) return a;
    return da < db ? a : b;
  });
  const maxEnd = ends.reduce((a, b) => {
    const da = parseIsoDate(a);
    const db = parseIsoDate(b);
    if (!da) return b;
    if (!db) return a;
    return da > db ? a : b;
  });
  return inSprint.filter((r) => {
    const assigned = getDateAssigned(r);
    const d = parseIsoDate(assigned);
    const start = parseIsoDate(minStart);
    const end = parseIsoDate(maxEnd);
    if (!start || !end) return true;
    if (!d) return false;
    return d >= start && d <= end;
  });
}

function statusCompletionPct(rows: JiraIssue[]): number {
  if (rows.length === 0) return 0;
  const done = rows.filter((r) => normalizeStatus(r.status) === "Done").length;
  return Math.round((done / rows.length) * 100);
}
type Page = "intake" | "complete-stories" | "view-dsr" | "wsr-generate" | "wsr-view";

// ─── WSR types ────────────────────────────────────────────────────
interface WsrStory {
  key: string;
  summary: string;
  type: "Story" | "Bug" | "Task" | "Spike";
  status: "Done" | "In Progress" | "To Do";
  assignee: string;
  points: number | null;
}
interface WsrSprint {
  id: string;
  name: string;
  location: string;
  start: string;
  end: string;
  stories: WsrStory[];
  nextWeek: string[];
}
interface WsrTrack {
  id: string;
  name: string;
  /** Jira project key for this track (e.g. COST, LOC) — used for DSR / ticket mapping */
  projectKey: string;
  fullName: string;
  tech: string;
  sprints: WsrSprint[];
}

/** Tracks from intake JSON (`tracks` field); codes are Jira project keys belonging to the track */
interface ImportedTrack {
  id: string;
  name: string;
  codes: string[];
  fullName?: string;
  tech?: string;
  /** DB project_id from /api/teams/{team}/tracks */
  projectId?: number;
  /** assignee name → reportee (manager) for DSR / Complete Stories */
  reportees?: Record<string, string>;
}

function enrichTracksWithCatalog(
  tracks: ImportedTrack[],
  catalog: TrackListItem[],
): ImportedTrack[] {
  return tracks.map((t) => {
    if (t.projectId) return t;
    const code = t.codes[0]?.toUpperCase();
    const match = catalog.find((c) => c.project_key.toUpperCase() === code);
    return match ? { ...t, projectId: match.project_id } : t;
  });
}

function projectIdForTrackName(
  name: string,
  tracks: ImportedTrack[],
  catalog: TrackListItem[],
): number | null {
  const t = tracks.find((x) => x.name === name);
  if (!t) return null;
  if (t.projectId) return t.projectId;
  const code = t.codes[0]?.toUpperCase();
  return catalog.find((c) => c.project_key.toUpperCase() === code)?.project_id ?? null;
}

/** Unique tracks from story rows (latest snapshot per key is enough for the filter list). */
function tracksFromStoryRecords(rows: JiraStoryRecord[]): ImportedTrack[] {
  const byKey = new Map<string, ImportedTrack>();
  for (const row of rows) {
    const pk = (row.project_key ?? "").trim();
    if (!pk) continue;
    const upper = pk.toUpperCase();
    if (byKey.has(upper)) continue;
    const name = (row.project_name ?? pk).trim() || pk;
    byKey.set(upper, {
      id: `db-${pk}`,
      name,
      codes: [pk],
      fullName: name,
      projectId: row.project_id,
    });
  }
  return [...byKey.values()].sort((a, b) => a.name.localeCompare(b.name));
}

const WSR_TRACKS: WsrTrack[] = [
  {
    id: "cost", name: "Cost", projectKey: "COST", fullName: "Cost Core Service", tech: "CHEDR (Haskell)",
    sprints: [
      {
        id: "cost-s1", name: "Sulphur Springs", location: "Sulphur Springs", start: "May 27", end: "Jun 9",
        stories: [
          { key: "COST-5402", summary: "Negotiate same day effective COGS contract with DCM for Bill Cost and Buyer Funding", type: "Story", status: "Done", assignee: "Rishi Manoj", points: 3 },
          { key: "COST-5403", summary: "Expose multiple-item DSD ledger endpoint", type: "Story", status: "Done", assignee: "Rishi Manoj", points: 2 },
          { key: "COST-5404", summary: "Mark unused endpoints deprecated and send initial communication", type: "Story", status: "Done", assignee: "Danny Baggett", points: 1 },
          { key: "COST-5405", summary: "Fix Confluence publisher", type: "Bug", status: "In Progress", assignee: "Danny Baggett", points: 1 },
          { key: "COST-5406", summary: "Finalize cash discount logic", type: "Story", status: "In Progress", assignee: "Rishi Manoj", points: 3 },
          { key: "COST-5407", summary: "Update /proposals/transitions to accept and send break-pack cost to DCM", type: "Story", status: "In Progress", assignee: "Danny Baggett", points: 2 },
          { key: "COST-5408", summary: "Backfill EDBI with deleted ledgers (DSD)", type: "Story", status: "In Progress", assignee: "Rishi Manoj", points: 2 },
          { key: "COST-5409", summary: "Investigate missing Basket, Offer and Account Master rows in CDC table", type: "Spike", status: "In Progress", assignee: "Danny Baggett", points: 2 },
          { key: "COST-5410", summary: "Handle Store -> LOB Changes in DSD RCQ Pipeline", type: "Story", status: "In Progress", assignee: "Rishi Manoj", points: 3 },
          { key: "COST-5411", summary: "Production support request - Investigate timeout on /v1/active-ledgers-by-date/dsd endpoint", type: "Task", status: "In Progress", assignee: "Danny Baggett", points: null },
        ],
        nextWeek: [
          "Research async process for providing supplier catalog",
          "Production support request - Fix Up CDC History Part 2",
        ],
      },
    ],
  },
  {
    id: "pricing", name: "Pricing", projectKey: "PRC", fullName: "Pricing Core Service", tech: "Haskell and Java",
    sprints: [
      {
        id: "pricing-s1", name: "PRC Sprint 18", location: "Nacogdoches", start: "May 14", end: "May 28",
        stories: [
          { key: "PRC-1120", summary: "Dynamic pricing engine integration with cost feed", type: "Story", status: "Done", assignee: "Ananya Mehta", points: 5 },
          { key: "PRC-1121", summary: "Price override audit log UI for store managers", type: "Story", status: "Done", assignee: "Kevin Loh", points: 3 },
          { key: "PRC-1122", summary: "Fix rounding issue in promotional price calculation", type: "Bug", status: "Done", assignee: "Ananya Mehta", points: 1 },
          { key: "PRC-1123", summary: "Price ladder configuration portal V2", type: "Story", status: "In Progress", assignee: "Kevin Loh", points: 5 },
          { key: "PRC-1124", summary: "Competitor price feed ingestion pipeline", type: "Story", status: "In Progress", assignee: "Ananya Mehta", points: 3 },
        ],
        nextWeek: [
          "Complete price ladder configuration portal",
          "Begin promotional pricing A/B testing framework",
          "Review price feed SLA with data team",
        ],
      },
    ],
  },
  {
    id: "locations", name: "Locations", projectKey: "LOC", fullName: "Location Core Service", tech: "Java and Angular",
    sprints: [
      {
        id: "loc-s1", name: "Q2.13FY26 Eridanus", location: "Eridanus", start: "Apr 16", end: "Apr 30",
        stories: [
          { key: "LOC-2357", summary: "FAM | Mainframe retirement | Warehouse - List Page | UI", type: "Story", status: "Done", assignee: "Vineed Kaladharan", points: 3 },
          { key: "LOC-2362", summary: "FAM | MFR | Warehouse - Create Warehouse - UI", type: "Story", status: "Done", assignee: "Vineed Kaladharan", points: 3 },
          { key: "LOC-2367", summary: "FAM | MFR | Warehouse - Edit Warehouse - UI", type: "Story", status: "Done", assignee: "Vineed Kaladharan", points: 3 },
        ],
        nextWeek: [
          "Begin Offsite Warehouse API integration",
          "Code review for warehouse edit flow",
        ],
      },
      {
        id: "loc-s2", name: "Q2.14 FY26 Fornax", location: "Fornax", start: "Apr 30", end: "May 14",
        stories: [
          { key: "LOC-2630", summary: "FAM | MFR | Analysis - Message sent to WPUD520 AND WPUD670", type: "Spike", status: "Done", assignee: "Vignesh Krishnan", points: 3 },
          { key: "LOC-2659", summary: "FAM | MFR | Warehouse - Create Offsite Warehouse - Save FAM-API", type: "Story", status: "Done", assignee: "Vignesh Krishnan", points: 3 },
          { key: "LOC-2660", summary: "FAM | MFR | Warehouse - Edit Offsite Warehouses - Save FAM-API", type: "Story", status: "Done", assignee: "Vignesh Krishnan", points: 3 },
          { key: "LOC-2724", summary: "Document VSAM/EMD integration - Main Warehouse and Offsite Warehouse", type: "Story", status: "Done", assignee: "Vignesh Krishnan", points: 2 },
          { key: "LOC-2738", summary: "FAM | MFR | Validation issues in Tobacco Permit and OMI Number fields", type: "Bug", status: "Done", assignee: "Vineed Kaladharan", points: null },
          { key: "LOC-2742", summary: "FAM | MFR | Validation issues: warehouse number length and tobacco permit", type: "Bug", status: "Done", assignee: "Vineed Kaladharan", points: null },
          { key: "LOC-2749", summary: "FAM | MFR | Status Column Displays X for Offsite Warehouses with New status", type: "Bug", status: "In Progress", assignee: "Vineed Kaladharan", points: null },
          { key: "LOC-2750", summary: "FAM | MFR | Offsite Warehouse List sorted by Offsite Number instead of creation date", type: "Bug", status: "In Progress", assignee: "Vineed Kaladharan", points: null },
        ],
        nextWeek: [
          "Complete bug fixes for offsite warehouse status column",
          "Begin VSAM integration testing in CERT environment",
          "Review EMD message format documentation",
        ],
      },
    ],
  },
  {
    id: "spur", name: "SPUR", projectKey: "SPUR", fullName: "Supplier Core Service – QA and SPUR", tech: "Haskell",
    sprints: [
      {
        id: "spur-s1", name: "SPUR Sprint 22", location: "Nacogdoches", start: "Apr 16", end: "Apr 30",
        stories: [
          { key: "SPUR-441", summary: "Supplier unit reconciliation batch job scheduling refactor", type: "Story", status: "Done", assignee: "Priya Nambiar", points: 3 },
          { key: "SPUR-442", summary: "Unit of measure conversion table migration to new schema", type: "Story", status: "Done", assignee: "Priya Nambiar", points: 2 },
          { key: "SPUR-443", summary: "Fix null pointer in SPUR event consumer on empty payload", type: "Bug", status: "In Progress", assignee: "Tom Alves", points: 1 },
          { key: "SPUR-444", summary: "QA automation suite for supplier unit reconciliation", type: "Task", status: "In Progress", assignee: "Tom Alves", points: 3 },
        ],
        nextWeek: [
          "Complete QA automation suite",
          "Fix null pointer and regression test",
          "Coordinate UAT with supplier ops team",
        ],
      },
    ],
  },
  {
    id: "supplier", name: "Supplier", projectKey: "SUP", fullName: "Supplier Core Service", tech: "Haskell",
    sprints: [
      {
        id: "sup-s1", name: "Sprint SUP-14", location: "Lufkin", start: "Apr 30", end: "May 14",
        stories: [
          { key: "SUP-883", summary: "EDI 850 inbound purchase order parser upgrade to v4 spec", type: "Story", status: "Done", assignee: "Laura Chen", points: 5 },
          { key: "SUP-884", summary: "Supplier contact deduplication logic using Levenshtein distance", type: "Story", status: "Done", assignee: "Miguel Santos", points: 2 },
          { key: "SUP-885", summary: "Fix ASN acknowledgement timeout not retrying on 503", type: "Bug", status: "Done", assignee: "Miguel Santos", points: 1 },
          { key: "SUP-882", summary: "Supplier onboarding self-service portal V2 - document upload", type: "Story", status: "In Progress", assignee: "Laura Chen", points: 8 },
          { key: "SUP-886", summary: "Supplier catalog sync to pricing feed on item update", type: "Story", status: "In Progress", assignee: "Laura Chen", points: 3 },
        ],
        nextWeek: [
          "Complete supplier self-service portal document upload",
          "Implement catalog sync retry with exponential backoff",
          "EDI 856 outbound ASN implementation kickoff",
        ],
      },
    ],
  },
  {
    id: "wentforth", name: "Wentforth", projectKey: "WNF", fullName: "Wentforth", tech: "Haskell",
    sprints: [
      {
        id: "wnf-s1", name: "WNF Sprint 9", location: "Wentforth", start: "Apr 16", end: "Apr 30",
        stories: [
          { key: "WNF-201", summary: "Wentforth store profile sync with master data service", type: "Story", status: "Done", assignee: "Sara Kim", points: 3 },
          { key: "WNF-202", summary: "Wentforth loyalty points redemption API integration", type: "Story", status: "Done", assignee: "Sara Kim", points: 5 },
          { key: "WNF-203", summary: "Fix loyalty expiry notification batch race condition", type: "Bug", status: "In Progress", assignee: "James Park", points: 2 },
          { key: "WNF-204", summary: "Wentforth store configuration export utility", type: "Task", status: "In Progress", assignee: "James Park", points: 1 },
        ],
        nextWeek: [
          "Fix race condition in loyalty expiry batch",
          "Complete store configuration export",
          "Loyalty program Q3 capacity planning",
        ],
      },
    ],
  },
  {
    id: "pharmacy", name: "Pharmacy", projectKey: "PHRM", fullName: "Pharmacy and Wellness", tech: "QA",
    sprints: [
      {
        id: "phrm-s1", name: "PHRM Sprint 11", location: "Pharr", start: "Apr 30", end: "May 14",
        stories: [
          { key: "PHRM-310", summary: "Prescription refill workflow redesign with patient-facing UI", type: "Story", status: "Done", assignee: "Dr. Aisha Patel", points: 5 },
          { key: "PHRM-311", summary: "Controlled substance DEA number validation at point of sale", type: "Story", status: "Done", assignee: "Dr. Aisha Patel", points: 3 },
          { key: "PHRM-313", summary: "Fix drug interaction alert false positives for common OTC combos", type: "Bug", status: "Done", assignee: "Ben Okafor", points: 2 },
          { key: "PHRM-312", summary: "Insurance eligibility check real-time API via CoverMyMeds", type: "Story", status: "In Progress", assignee: "Ben Okafor", points: 5 },
          { key: "PHRM-314", summary: "QA regression suite for prescription refill flow", type: "Task", status: "In Progress", assignee: "Dr. Aisha Patel", points: 3 },
        ],
        nextWeek: [
          "Complete insurance eligibility real-time API integration",
          "Full QA regression run on refill workflow",
          "Pharmacy compliance review with legal",
        ],
      },
    ],
  },
  {
    id: "gss", name: "GSS", projectKey: "GSS", fullName: "Global Sourcing Solution", tech: "Java",
    sprints: [
      {
        id: "gss-s1", name: "GSS Sprint 7", location: "Georgetown", start: "Apr 16", end: "Apr 30",
        stories: [
          { key: "GSS-155", summary: "Global store setup configuration export tool for onboarding", type: "Story", status: "Done", assignee: "Carlos Rivera", points: 3 },
          { key: "GSS-157", summary: "Fix store timezone mismatch in schedule export report", type: "Bug", status: "Done", assignee: "Fatima Al-Rashid", points: 1 },
          { key: "GSS-158", summary: "GSS audit trail enhancement for config changes", type: "Story", status: "Done", assignee: "Fatima Al-Rashid", points: 2 },
          { key: "GSS-156", summary: "Multi-region store attribute inheritance engine", type: "Story", status: "In Progress", assignee: "Carlos Rivera", points: 8 },
          { key: "GSS-159", summary: "Supplier catalog mapping to GSS item codes", type: "Story", status: "In Progress", assignee: "Carlos Rivera", points: 5 },
        ],
        nextWeek: [
          "Complete multi-region store attribute inheritance engine",
          "Begin supplier catalog mapping integration testing",
          "GSS performance benchmarking for 500+ store configs",
        ],
      },
    ],
  },
];

// Map project_key → track name (WSR defaults) when a ticket is not covered by imported `tracks`
const PROJECT_KEY_TO_TRACK: Record<string, string> = Object.fromEntries(
  WSR_TRACKS.map((t) => [t.projectKey, t.name]),
);
const trackName = (key: string) => PROJECT_KEY_TO_TRACK[key] ?? key;

function inferTracksFromTickets(rows: JiraIssue[]): ImportedTrack[] {
  const byKey = new Map<string, string>();
  for (const r of rows) {
    const pk = (r.project_key ?? "").trim();
    if (!pk) continue;
    const pn = (r.project_name ?? pk).trim();
    if (!byKey.has(pk)) byKey.set(pk, pn);
  }
  return [...byKey.entries()].map(([pk, name], i) => ({
    id: `inferred-${pk}-${i}`,
    name,
    codes: [pk],
  }));
}

function normalizeTrackCodes(v: unknown): string[] {
  if (v == null) return [];
  if (Array.isArray(v)) return v.flatMap((x) => normalizeTrackCodes(x));
  if (typeof v === "string")
    return v.split(/[,;\s]+/).map((s) => s.trim()).filter(Boolean);
  return [];
}

function parseReporteeMapFromObject(raw: unknown): Record<string, string> | undefined {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return undefined;
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (typeof v === "string" && v.trim() && k.trim()) out[k.trim()] = v.trim();
  }
  return Object.keys(out).length > 0 ? out : undefined;
}

function parseReporteeMapFromTrack(o: Record<string, unknown>): Record<string, string> | undefined {
  const direct = parseReporteeMapFromObject(
    o.reportees ?? o.reportee_map ?? o.assignee_reportees,
  );
  if (direct) return direct;

  const members = o.members;
  if (!Array.isArray(members)) return undefined;
  const out: Record<string, string> = {};
  for (const m of members) {
    if (!m || typeof m !== "object") continue;
    const mo = m as Record<string, unknown>;
    const assignee = [mo.assignee, mo.name, mo.member].find(
      (x) => typeof x === "string" && String(x).trim(),
    ) as string | undefined;
    const reportee = [mo.reportee, mo.manager, mo.lead, mo.reports_to, mo.reportsTo].find(
      (x) => typeof x === "string" && String(x).trim(),
    ) as string | undefined;
    if (assignee && reportee) out[assignee.trim()] = reportee.trim();
  }
  return Object.keys(out).length > 0 ? out : undefined;
}

function inferReporteeMapFromTickets(tickets: JiraIssue[]): Record<string, string> {
  const byAssignee = new Map<string, Map<string, number>>();
  for (const t of tickets) {
    const assignee = t.assignee?.trim();
    if (!assignee) continue;
    const candidate = t.reportee?.trim() || t.reporter?.trim();
    if (!candidate || candidate === assignee) continue;
    if (!byAssignee.has(assignee)) byAssignee.set(assignee, new Map());
    const counts = byAssignee.get(assignee)!;
    counts.set(candidate, (counts.get(candidate) ?? 0) + 1);
  }
  const out: Record<string, string> = {};
  for (const [assignee, counts] of byAssignee) {
    let best = "";
    let bestN = 0;
    for (const [rep, n] of counts) {
      if (n > bestN) {
        best = rep;
        bestN = n;
      }
    }
    if (best) out[assignee] = best;
  }
  return out;
}

function buildReporteeMap(tracks: ImportedTrack[], tickets: JiraIssue[]): Record<string, string> {
  const map: Record<string, string> = {};
  for (const track of tracks) {
    if (track.reportees) Object.assign(map, track.reportees);
  }
  for (const row of tickets) {
    const assignee = row.assignee?.trim();
    const reportee = row.reportee?.trim();
    if (assignee && reportee) map[assignee] = reportee;
  }
  const inferred = inferReporteeMapFromTickets(tickets);
  for (const [assignee, reportee] of Object.entries(inferred)) {
    if (!map[assignee]) map[assignee] = reportee;
  }
  return map;
}

function getReporteeForAssignee(
  assignee: string | undefined | null,
  reporteeMap: Record<string, string>,
): string {
  const key = assignee?.trim();
  if (!key) return "—";
  return reporteeMap[key] ?? "—";
}

function parseImportedTracks(raw: unknown[]): ImportedTrack[] {
  const out: ImportedTrack[] = [];
  raw.forEach((item, i) => {
    if (!item || typeof item !== "object") return;
    const o = item as Record<string, unknown>;
    const name = [o.name, o.track_name, o.title, o.label, o.trackName].find(
      (x) => typeof x === "string" && String(x).trim(),
    ) as string | undefined;
    if (!name?.trim()) return;
    let codes = normalizeTrackCodes(
      o.codes ?? o.project_keys ?? o.track_codes ?? o.projects ?? o.keys ?? o.projectKeys,
    );
    if (codes.length === 0) {
      const single = [o.code, o.project_key, o.track_code].find(
        (x) => typeof x === "string" && String(x).trim(),
      ) as string | undefined;
      if (single) codes = [single.trim()];
    }
    const idRaw = o.id;
    const id = typeof idRaw === "string" && idRaw.trim() ? idRaw.trim() : `track-${i}-${name.trim()}`;
    const reportees = parseReporteeMapFromTrack(o);
    out.push({
      id,
      name: name.trim(),
      codes,
      fullName:
        typeof o.full_name === "string"
          ? o.full_name
          : typeof o.fullName === "string"
            ? o.fullName
            : undefined,
      tech: typeof o.tech === "string" ? o.tech : undefined,
      reportees,
    });
  });
  return out;
}

function splitImportPayload(data: unknown): { rows: JiraIssue[]; tracks: ImportedTrack[] } {
  if (Array.isArray(data)) {
    const rows = data as JiraIssue[];
    return { rows, tracks: inferTracksFromTickets(rows) };
  }
  if (data && typeof data === "object") {
    const o = data as Record<string, unknown>;
    const arrKeys = ["tickets", "issues", "rows", "items", "data"];
    let rows: JiraIssue[] = [];
    for (const k of arrKeys) {
      const v = o[k];
      if (Array.isArray(v)) {
        rows = v as JiraIssue[];
        break;
      }
    }
    const tracksRaw = o.tracks;
    let tracks: ImportedTrack[] = Array.isArray(tracksRaw) ? parseImportedTracks(tracksRaw as unknown[]) : [];
    if (tracks.length === 0) tracks = inferTracksFromTickets(rows);
    const rootReportees = parseReporteeMapFromObject(o.reportees ?? o.reportee_map ?? o.assignee_reportees);
    if (rootReportees) {
      tracks = tracks.map((t) => ({
        ...t,
        reportees: { ...rootReportees, ...t.reportees },
      }));
    }
    return { rows, tracks };
  }
  return { rows: [], tracks: [] };
}

interface StoredBundle {
  tickets: JiraIssue[];
  tracks: ImportedTrack[];
}

function wsrTracksAsImported(): ImportedTrack[] {
  return WSR_TRACKS.map((t) => ({
    id: t.id,
    name: t.name,
    codes: [t.projectKey],
    fullName: t.fullName,
    tech: t.tech,
  }));
}

function displayTrackName(projectKey: string, tracks: ImportedTrack[]): string {
  const u = projectKey.toUpperCase();
  for (const t of tracks) {
    if (t.codes.some((c) => c.toUpperCase() === u)) return t.name;
  }
  return trackName(projectKey);
}

function pickCurrentSprintName(rows: JiraIssue[]): string {
  if (rows.length === 0) return "";
  const bySprint = new Map<string, JiraIssue[]>();
  for (const r of rows) {
    const s = r.sprint_name?.trim() || "(no sprint)";
    if (!bySprint.has(s)) bySprint.set(s, []);
    bySprint.get(s)!.push(r);
  }
  let best = "";
  let bestN = -1;
  let bestEnd = 0;
  for (const [name, list] of bySprint) {
    const n = list.length;
    const ends = list.map((l) => l.sprint_end_date).filter(Boolean) as string[];
    const maxEnd = ends.length
      ? Math.max(...ends.map((d) => new Date(d + "T12:00:00").getTime()))
      : 0;
    if (n > bestN || (n === bestN && maxEnd > bestEnd)) {
      best = name;
      bestN = n;
      bestEnd = maxEnd;
    }
  }
  return best === "(no sprint)" ? "" : best;
}

function sprintDateRangeForName(rows: JiraIssue[], sprintName: string): string {
  const sub = rows.filter((r) => r.sprint_name === sprintName);
  if (sub.length === 0) return "";
  const starts = sub.map((r) => r.sprint_start_date).filter(Boolean) as string[];
  const ends = sub.map((r) => r.sprint_end_date).filter(Boolean) as string[];
  if (!starts.length && !ends.length) return "";
  const minS = starts.length
    ? Math.min(...starts.map((d) => new Date(d + "T12:00:00").getTime()))
    : null;
  const maxE = ends.length
    ? Math.max(...ends.map((d) => new Date(d + "T12:00:00").getTime()))
    : null;
  if (minS != null && maxE != null)
    return `${fmtDateShort(new Date(minS))} – ${fmtDateShort(new Date(maxE))}`;
  return "";
}

// Build slides array from tracks
interface WsrSlide {
  slideNum: number;
  type: "index" | "track";
  label: string;
  trackId?: string;
  sprintId?: string;
}

function buildWsrSlides(): WsrSlide[] {
  const slides: WsrSlide[] = [{ slideNum: 1, type: "index", label: "Index" }];
  let num = 2;
  for (const track of WSR_TRACKS) {
    for (const sprint of track.sprints) {
      const label = track.sprints.length > 1
        ? `${track.fullName} (${sprint.name})`
        : track.fullName;
      slides.push({ slideNum: num++, type: "track", label, trackId: track.id, sprintId: sprint.id });
    }
  }
  return slides;
}

const LS_KEY = "statusforge_tickets";

function loadFromStorage(): StoredBundle {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { tickets: [], tracks: [] };
    const data = JSON.parse(raw) as unknown;
    if (Array.isArray(data)) {
      const tickets = data as JiraIssue[];
      return { tickets, tracks: inferTracksFromTickets(tickets) };
    }
    if (data && typeof data === "object") {
      const o = data as Record<string, unknown>;
      const t = o.tickets;
      const rows = Array.isArray(t) ? (t as JiraIssue[]) : [];
      const tracksRaw = o.tracks;
      const tracks = Array.isArray(tracksRaw)
        ? parseImportedTracks(tracksRaw as unknown[])
        : inferTracksFromTickets(rows);
      return { tickets: rows, tracks };
    }
    return { tickets: [], tracks: [] };
  } catch {
    return { tickets: [], tracks: [] };
  }
}

function saveToStorage(tickets: JiraIssue[], tracks: ImportedTrack[]) {
  localStorage.setItem(LS_KEY, JSON.stringify({ tickets, tracks }));
}

// ─── WSR report persistence ───────────────────────────────────────
const WSR_LS_KEY = "statusforge_wsr_reports";

interface SavedWsrReport {
  id: string;
  weekStart: string; // ISO date YYYY-MM-DD (always Monday)
  weekEnd: string;   // always Friday
  generatedAt: string;
  edits: Record<string, string>;
}

function loadWsrReports(): SavedWsrReport[] {
  try { return JSON.parse(localStorage.getItem(WSR_LS_KEY) ?? "[]"); } catch { return []; }
}

function saveWsrReport(report: SavedWsrReport) {
  const all = loadWsrReports().filter((r) => r.id !== report.id);
  localStorage.setItem(WSR_LS_KEY, JSON.stringify([report, ...all]));
}

// ─── Week date utilities ──────────────────────────────────────────
function getMondayOf(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay(); // 0=Sun
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function getFridayOf(monday: Date): Date {
  const d = new Date(monday);
  d.setDate(d.getDate() + 4);
  return d;
}

function fmtDate(d: Date): string {
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short", year: "numeric" });
}

function fmtDateShort(d: Date): string {
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function weekLabel(weekStart: string): string {
  const mon = new Date(weekStart + "T00:00:00");
  const fri = getFridayOf(mon);
  return `${fmtDate(mon)} – ${fmtDate(fri)}`;
}

function weekId(weekStart: string): string {
  return `wsr-${weekStart}`;
}

function StatusBadge({ status }: { status: string }) {
  const normalized = normalizeStatus(status);
  const map: Record<StoryStatus, string> = {
    Done: "bg-green-100 text-green-700 border border-green-200",
    "In Progress": "bg-blue-100 text-blue-700 border border-blue-200",
    "To Do": "bg-gray-100 text-gray-600 border border-gray-200",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${map[normalized]}`}
    >
      {normalized}
    </span>
  );
}

function IssueTypeBadge({ type }: { type: string }) {
  const map: Record<
    string,
    { cls: string; icon: React.ReactNode }
  > = {
    Bug: {
      cls: "bg-red-50 text-red-600 border border-red-200",
      icon: <Bug className="w-3 h-3" />,
    },
    Story: {
      cls: "bg-purple-50 text-purple-600 border border-purple-200",
      icon: <BookOpen className="w-3 h-3" />,
    },
    Spike: {
      cls: "bg-teal-50 text-teal-600 border border-teal-200",
      icon: <Zap className="w-3 h-3" />,
    },
    Task: {
      cls: "bg-brand-red/10 text-blue-600 border border-blue-200",
      icon: <ClipboardList className="w-3 h-3" />,
    },
  };
  const cfg = map[type] ?? {
    cls: "bg-gray-100 text-gray-600 border border-gray-200",
    icon: null,
  };
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${cfg.cls}`}
    >
      {cfg.icon}
      {type}
    </span>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const map: Record<string, string> = {
    Low: "bg-gray-100 text-gray-500 border border-gray-200",
    Medium:
      "bg-yellow-50 text-yellow-700 border border-yellow-200",
    High: "bg-orange-50 text-orange-700 border border-orange-200",
    Critical: "bg-red-100 text-red-700 border border-red-200",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${map[priority] ?? "bg-gray-100 text-gray-500 border border-gray-200"}`}
    >
      {priority}
    </span>
  );
}

function Select({
  value,
  onChange,
  options,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
  placeholder: string;
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full appearance-none bg-white border border-gray-200 rounded-md px-3 py-1.5 pr-7 text-sm text-gray-700 focus:outline-none focus:ring-1 focus:ring-brand-red/40 cursor-pointer"
      >
        <option value="">{placeholder}</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
      <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 pointer-events-none" />
    </div>
  );
}

function IdSelect({
  value,
  onChange,
  options,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { id: number; label: string }[];
  placeholder: string;
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full appearance-none bg-white border border-gray-200 rounded-md px-3 py-1.5 pr-7 text-sm text-gray-700 focus:outline-none focus:ring-1 focus:ring-brand-red/40 cursor-pointer"
      >
        <option value="">{placeholder}</option>
        {options.map((o) => (
          <option key={o.id} value={String(o.id)}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 pointer-events-none" />
    </div>
  );
}

function DsrEditableInput({
  value,
  onSave,
  className = "",
  type = "text",
}: {
  value: string;
  onSave: (v: string) => void;
  className?: string;
  type?: string;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  return (
    <input
      type={type}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        if (draft !== value) onSave(draft);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
      }}
      className={`w-full min-w-0 px-2 py-1 border border-transparent hover:border-gray-200 focus:border-brand-red/40 rounded text-xs bg-transparent focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-red/30 ${className}`}
    />
  );
}

function DsrEditableStatus({
  value,
  onSave,
}: {
  value: string;
  onSave: (v: string) => void;
}) {
  return (
    <select
      value={normalizeStatus(value)}
      onChange={(e) => onSave(e.target.value)}
      className="px-2 py-1 border border-gray-200 rounded text-xs bg-white focus:outline-none focus:ring-1 focus:ring-brand-red/30"
    >
      <option value="To Do">To Do</option>
      <option value="In Progress">In Progress</option>
      <option value="Done">Done</option>
    </select>
  );
}

function newDraftStory(track: ImportedTrack): JiraStoryRecord {
  const code = track.codes[0] ?? "NEW";
  const today = todayIsoDate();
  return {
    jira_key: `${code}-NEW-${Date.now()}`,
    project_key: code,
    project_name: track.fullName ?? track.name,
    sprint_name: "",
    sprint_start_date: "",
    sprint_end_date: "",
    summary: "Story",
    description: "",
    title: "",
    issue_type: "Story",
    priority: "Medium",
    assignee: "",
    reporter: "",
    status: "To Do",
    story_points: null,
    created_date: today,
    date_assigned: today,
    updated_date: today,
    resolved_date: null,
    snapshot_date: today,
    isDraft: true,
  };
}

function Stepper({ step }: { step: number }) {
  const steps = ["Import JSON", "Review & Edit (Rows)", "Summary"];
  return (
    <div className="flex items-center gap-0">
      {steps.map((label, i) => {
        const idx = i + 1;
        const active = idx === step;
        const done = idx < step;
        return (
          <div key={label} className="flex items-center">
            <div
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium ${active ? "text-brand-red" : done ? "text-green-600" : "text-gray-400"}`}
            >
              <span
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold border-2 ${active ? "border-brand-red bg-brand-red text-white" : done ? "border-green-500 bg-green-100 text-green-600" : "border-gray-300 text-gray-400"}`}
              >
                {done ? (
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                ) : (
                  idx
                )}
              </span>
              {label}
            </div>
            {i < steps.length - 1 && (
              <svg className="w-5 h-5 text-gray-300 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
            )}
          </div>
        );
      })}
    </div>
  );
}

function DSREntryPage({
  onImportComplete,
  onViewSavedTickets,
  trackCatalog,
  onTracksChanged,
}: {
  onImportComplete: (rows: JiraIssue[], tracks: ImportedTrack[]) => void;
  onViewSavedTickets: () => void;
  trackCatalog: TrackListItem[];
  onTracksChanged: () => void;
}) {
  const [step, setStep] = useState(1);
  const [jsonText, setJsonText] = useState("");
  const [parsedRows, setParsedRows] = useState<JiraIssue[]>([]);
  const [parsedTracks, setParsedTracks] = useState<ImportedTrack[]>([]);
  const [parseError, setParseError] = useState("");
  const [savedCount, setSavedCount] = useState(0);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState("");
  const [search, setSearch] = useState("");
  const [selectedRows, setSelectedRows] = useState<Set<number>>(
    new Set(),
  );
  const [editCell, setEditCell] = useState<{
    row: number;
    col: string;
  } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const parseJson = (text: string) => {
    try {
      const data = JSON.parse(text);
      const { rows, tracks } = splitImportPayload(data);
      setParsedRows(rows);
      setParsedTracks(tracks);
      setParseError("");
      setStep(2);
    } catch {
      setParseError(
        "Invalid JSON. Please check the format and try again.",
      );
    }
  };

  const handleFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      setJsonText(text);
      parseJson(text);
    };
    reader.readAsText(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, []);

  const loadSample = () => {
    const text = JSON.stringify(SAMPLE_DATA, null, 2);
    setJsonText(text);
    parseJson(text);
  };

  const filtered = parsedRows.filter((r) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      r.jira_key?.toLowerCase().includes(q) ||
      r.summary?.toLowerCase().includes(q) ||
      r.description?.toLowerCase().includes(q) ||
      r.assignee?.toLowerCase().includes(q) ||
      (r.story_points != null && String(r.story_points).includes(q))
    );
  });

  const toggleRow = (i: number) => {
    const s = new Set(selectedRows);
    s.has(i) ? s.delete(i) : s.add(i);
    setSelectedRows(s);
  };

  const deleteSelected = () => {
    setParsedRows((prev) =>
      prev.filter((_, i) => !selectedRows.has(i)),
    );
    setSelectedRows(new Set());
  };

  const addRow = () => {
    const blank: JiraIssue = {
      project_key: "",
      project_name: "",
      sprint_name: "",
      sprint_start_date: "",
      sprint_end_date: "",
      jira_key: "",
      summary: "",
      description: "",
      issue_type: "Story",
      priority: "Low",
      assignee: "",
      reporter: "",
      status: "To Do",
      story_points: null,
      created_date: "",
      updated_date: "",
      resolved_date: null,
      snapshot_date: new Date().toISOString().split("T")[0],
    };
    setParsedRows((prev) => [...prev, blank]);
  };

  const exportJson = () => {
    const payload = { tickets: parsedRows, tracks: parsedTracks };
    const blob = new Blob(
      [JSON.stringify(payload, null, 2)],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "jira-report.json";
    a.click();
  };

  const updateCell = (
    rowIdx: number,
    col: string,
    val: string,
  ) => {
    setParsedRows((prev) =>
      prev.map((r, i) => {
        if (i !== rowIdx) return r;
        if (col === "story_points") {
          const trimmed = val.trim();
          if (trimmed === "") return { ...r, story_points: null };
          const n = Number(trimmed);
          return { ...r, story_points: Number.isNaN(n) ? r.story_points : n };
        }
        return { ...r, [col]: val };
      }),
    );
  };

  const COLS: {
    key: keyof JiraIssue;
    label: string;
    w: string;
  }[] = [
    { key: "project_key", label: "Project Key", w: "w-24" },
    { key: "project_name", label: "Project Name", w: "w-28" },
    { key: "sprint_name", label: "Sprint Name", w: "w-36" },
    { key: "date_assigned", label: "Date Assigned", w: "w-28" },
    { key: "jira_key", label: "Jira Key", w: "w-24" },
    { key: "summary", label: "Summary", w: "w-72" },
    { key: "description", label: "Description", w: "w-96" },
    { key: "issue_type", label: "Issue Type", w: "w-24" },
    { key: "priority", label: "Priority", w: "w-20" },
    { key: "status", label: "Status", w: "w-24" },
    { key: "story_points", label: "Story Points", w: "w-20" },
    { key: "assignee", label: "Assignee", w: "w-36" },
    { key: "reporter", label: "Reporter", w: "w-36" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-400 font-medium">
            ←
          </span>
          <h1 className="text-base font-semibold text-gray-800">
            DSR — JSON Import to Entry
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-gray-400">
            DSR DATE
          </span>
          <span className="text-sm font-medium text-gray-700 flex items-center gap-1">
            <Calendar className="w-4 h-4 text-gray-400" />
            17 Jun, 2026
          </span>
        </div>
      </div>

      {/* Stepper */}
      <div className="flex items-center px-6 py-3 border-b border-gray-100 bg-white">
        <Stepper step={step} />
      </div>

      <div className="flex flex-1 min-h-0 relative">
        <div className="flex-1 flex flex-col min-h-0 min-w-0 w-full">
      {step === 1 && (
        <div className="flex-1 flex flex-col p-6 gap-6 min-h-0">
          <div className="flex gap-6 flex-1 min-h-0">
            {/* Paste JSON */}
            <div className="flex-1 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-semibold text-gray-700">
                  PASTE JSON
                </label>
                <button
                  onClick={loadSample}
                  className="text-xs text-brand-red hover:text-brand-red-dark underline"
                >
                  Load sample data
                </button>
              </div>
              <textarea
                value={jsonText}
                onChange={(e) => setJsonText(e.target.value)}
                className="flex-1 font-mono text-xs bg-gray-900 text-green-400 rounded-lg p-4 resize-none focus:outline-none focus:ring-2 focus:ring-brand-red/40 border border-gray-700 min-h-64"
                placeholder={
                  '{\n  "tracks": [\n    { "name": "Cost", "codes": ["COST"] }\n  ],\n  "tickets": [\n    { "project_key": "COST", "jira_key": "COST-1234", ... }\n  ]\n}\n\nOr a plain array of ticket objects (tracks are inferred from project keys).'
                }
              />
              {parseError && (
                <p className="text-xs text-red-500">
                  {parseError}
                </p>
              )}
              <p className="text-xs text-gray-400">
                Paste/Edit here the JSON from Rovo AI · 0 rows
              </p>
            </div>

            {/* Upload */}
            <div className="w-64 flex flex-col gap-2">
              <label className="text-sm font-semibold text-gray-700">
                OR UPLOAD JSON FILE
              </label>
              <div
                onDrop={handleDrop}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                className={`flex-1 min-h-64 border-2 border-dashed rounded-xl flex flex-col items-center justify-center gap-3 transition-colors cursor-pointer ${dragging ? "border-brand-red/50 bg-brand-red/10" : "border-gray-300 bg-gray-50 hover:bg-gray-100"}`}
                onClick={() => fileRef.current?.click()}
              >
                <Upload className="w-10 h-10 text-gray-400" />
                <p className="text-sm text-gray-500 text-center">
                  Drag & drop JSON file here
                </p>
                <button className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 shadow-sm">
                  Choose File
                </button>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".json"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleFile(f);
                  }}
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={() => parseJson(jsonText)}
              className="px-6 py-2 bg-brand-orange text-white rounded-lg text-sm font-medium hover:bg-brand-orange-hover transition-colors"
            >
              Parse & Continue →
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="flex-1 flex flex-col items-center justify-center p-8">
          <div className="bg-white border border-gray-200 rounded-2xl p-10 max-w-xl w-full">
            <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mb-6">
              <CheckCircle2 className="w-9 h-9 text-green-500" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">DSR saved</h2>
            <p className="text-gray-500 text-sm mb-8">
              <span className="font-semibold text-gray-800">{savedCount}</span> tickets captured for{" "}
              <strong className="text-gray-900">17&nbsp;&nbsp;Jun&nbsp;&nbsp;2026</strong>. Open Story Board to browse and filter your tickets.
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  setStep(1);
                  setJsonText("");
                  setParsedRows([]);
                  setParsedTracks([]);
                  setParseError("");
                  setSelectedRows(new Set());
                  setSearch("");
                }}
                className="px-5 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Start a new DSR
              </button>
              <button
                onClick={onViewSavedTickets}
                className="px-5 py-2.5 bg-brand-orange text-white rounded-lg text-sm font-medium hover:bg-brand-orange-hover"
              >
                View Story Board
              </button>
            </div>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {/* Parsed Rows toolbar */}
          <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 bg-white">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-gray-700">
                Parsed Rows
              </span>
              <span className="text-xs text-gray-400">
                (auto-generated)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={addRow}
                className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded-md text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                <Plus className="w-3.5 h-3.5" /> Add Row
              </button>
              <button
                onClick={deleteSelected}
                disabled={selectedRows.size === 0}
                className="flex items-center gap-1.5 px-3 py-1.5 border border-red-200 rounded-md text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-40"
              >
                <Trash2 className="w-3.5 h-3.5" /> Delete Row
              </button>
              <button
                onClick={exportJson}
                className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded-md text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                <Download className="w-3.5 h-3.5" /> Export JSON
              </button>
              <button
                onClick={() => {
                  setParsedRows([]);
                  setParsedTracks([]);
                  setStep(1);
                  setJsonText("");
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded-md text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                <X className="w-3.5 h-3.5" /> Clear All
              </button>
              <div className="relative">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search..."
                  className="pl-7 pr-3 py-1.5 border border-gray-300 rounded-md text-xs focus:outline-none focus:ring-1 focus:ring-brand-red/40 w-44"
                />
              </div>
              <button className="p-1.5 border border-gray-300 rounded-md hover:bg-gray-50">
                <Filter className="w-3.5 h-3.5 text-gray-500" />
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="flex-1 overflow-auto">
            <table className="w-full text-xs border-collapse">
              <thead className="sticky top-0 bg-gray-50 z-10">
                <tr>
                  <th className="w-10 px-3 py-2 text-left border-b border-gray-200">
                    <input
                      type="checkbox"
                      className="rounded"
                      onChange={(e) => {
                        if (e.target.checked)
                          setSelectedRows(
                            new Set(filtered.map((_, i) => i)),
                          );
                        else setSelectedRows(new Set());
                      }}
                    />
                  </th>
                  <th className="w-8 px-2 py-2 text-left border-b border-gray-200 text-gray-500 font-medium">
                    #
                  </th>
                  {COLS.map((c) => (
                    <th
                      key={c.key}
                      className={`${c.w} px-3 py-2 text-left border-b border-gray-200 text-gray-500 font-medium whitespace-nowrap`}
                    >
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((row, i) => (
                  <tr
                    key={i}
                    className={`border-b border-gray-100 hover:bg-brand-red/10/30 ${selectedRows.has(i) ? "bg-brand-red/10" : ""}`}
                  >
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selectedRows.has(i)}
                        onChange={() => toggleRow(i)}
                        className="rounded"
                      />
                    </td>
                    <td className="px-2 py-2 text-gray-400">
                      {i + 1}
                    </td>
                    {COLS.map((c) => {
                      const val = row[c.key];
                      const isEditing =
                        editCell?.row === i &&
                        editCell?.col === c.key;
                      if (c.key === "status")
                        return (
                          <td key={c.key} className="px-3 py-2">
                            <StatusBadge
                              status={String(val ?? "")}
                            />
                          </td>
                        );
                      if (c.key === "issue_type")
                        return (
                          <td key={c.key} className="px-3 py-2">
                            <IssueTypeBadge
                              type={String(val ?? "")}
                            />
                          </td>
                        );
                      if (c.key === "priority")
                        return (
                          <td key={c.key} className="px-3 py-2">
                            <PriorityBadge
                              priority={String(val ?? "")}
                            />
                          </td>
                        );
                      if (c.key === "story_points")
                        return (
                          <td
                            key={c.key}
                            className="px-3 py-2 text-center"
                            onClick={() =>
                              setEditCell({ row: i, col: c.key })
                            }
                          >
                            {isEditing ? (
                              <input
                                autoFocus
                                type="number"
                                min={0}
                                step={0.5}
                                defaultValue={val != null ? String(val) : ""}
                                onBlur={(e) => {
                                  updateCell(i, c.key, e.target.value);
                                  setEditCell(null);
                                }}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") {
                                    updateCell(i, c.key, e.currentTarget.value);
                                    setEditCell(null);
                                  }
                                }}
                                className="w-14 border border-brand-red/50 rounded px-1 py-0.5 text-xs text-center focus:outline-none bg-white"
                              />
                            ) : val != null && val !== "" ? (
                              <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-brand-red/10 text-brand-red font-bold text-xs cursor-text">
                                {String(val)}
                              </span>
                            ) : (
                              <span className="text-gray-300 cursor-text">—</span>
                            )}
                          </td>
                        );
                      const isLongText = c.key === "summary" || c.key === "description";
                      return (
                        <td
                          key={c.key}
                          className={`px-3 py-2 ${isLongText ? "max-w-md" : ""}`}
                          onClick={() =>
                            setEditCell({ row: i, col: c.key })
                          }
                        >
                          {isEditing ? (
                            c.key === "description" ? (
                              <textarea
                                autoFocus
                                defaultValue={String(val ?? "")}
                                rows={3}
                                onBlur={(e) => {
                                  updateCell(
                                    i,
                                    c.key,
                                    e.target.value,
                                  );
                                  setEditCell(null);
                                }}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter" && e.ctrlKey) {
                                    updateCell(
                                      i,
                                      c.key,
                                      e.currentTarget.value,
                                    );
                                    setEditCell(null);
                                  }
                                }}
                                className="w-full min-w-64 border border-brand-red/50 rounded px-1 py-0.5 text-xs focus:outline-none bg-white resize-y"
                              />
                            ) : (
                            <input
                              autoFocus
                              defaultValue={String(val ?? "")}
                              onBlur={(e) => {
                                updateCell(
                                  i,
                                  c.key,
                                  e.target.value,
                                );
                                setEditCell(null);
                              }}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") {
                                  updateCell(
                                    i,
                                    c.key,
                                    e.currentTarget.value,
                                  );
                                  setEditCell(null);
                                }
                              }}
                              className="w-full border border-brand-red/50 rounded px-1 py-0.5 text-xs focus:outline-none bg-white"
                            />
                            )
                          ) : (
                            <span
                              className={`block truncate cursor-text text-gray-700 ${isLongText ? "max-w-md" : ""}`}
                              title={String(val ?? "")}
                            >
                              {val != null && val !== "" ? (
                                String(val)
                              ) : (
                                <span className="text-gray-300">
                                  —
                                </span>
                              )}
                            </span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            {filtered.length === 0 && (
              <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
                No rows to display
              </div>
            )}
          </div>

          {/* Footer actions */}
          <div className="flex items-center justify-between px-6 py-3 border-t border-gray-200 bg-white">
            <button
              onClick={() => setStep(1)}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
            >
              ← Back
            </button>

            <div className="flex items-center gap-2">
              {importError ? (
                <span className="text-xs text-red-500 max-w-xs truncate" title={importError}>
                  {importError}
                </span>
              ) : null}
              <span className="text-xs text-gray-400">
                {parsedRows.length} rows parsed
              </span>
              <button
                disabled={importing || parsedRows.length === 0}
                onClick={async () => {
                  setImporting(true);
                  setImportError("");
                  try {
                    const result = await importStories(parsedRows);
                    const rowsWithTitles = parsedRows.map((row) => {
                      const saved = result.stories.find((s) => s.jira_key === row.jira_key);
                      return saved?.title ? { ...row, title: saved.title } : row;
                    });
                    saveToStorage(rowsWithTitles, parsedTracks);
                    onImportComplete(rowsWithTitles, parsedTracks);
                    setSavedCount(rowsWithTitles.length);
                    setStep(3);
                  } catch (err) {
                    setImportError(err instanceof Error ? err.message : "Import failed");
                  } finally {
                    setImporting(false);
                  }
                }}
                className="px-5 py-2 bg-brand-orange text-white rounded-lg text-sm font-medium hover:bg-brand-orange-hover disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {importing ? "Saving & generating titles…" : "Generate Report →"}
              </button>
            </div>
          </div>
        </div>
      )}
        </div>
        <RovoRequestSidebar trackCatalog={trackCatalog} onTracksChanged={onTracksChanged} />
      </div>
    </div>
  );
}

function SavedTicketsPage({
  tracks: _savedTracks,
  trackCatalog,
}: {
  tracks: ImportedTrack[];
  trackCatalog: TrackListItem[];
}) {
  const [dbTrackList, setDbTrackList] = useState<ImportedTrack[]>([]);

  const uiTracks = useMemo(
    () => enrichTracksWithCatalog(
      dbTrackList.length > 0
        ? dbTrackList
        : catalogToImportedTracks(trackCatalog),
      trackCatalog,
    ),
    [dbTrackList, trackCatalog],
  );

  const trackOptions = uiTracks.map((t) => t.name);

  const [allData, setAllData] = useState<JiraStoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState("");
  const [filterTrack, setFilterTrack] = useState("");
  const [filterAssignee, setFilterAssignee] = useState("");
  const [filterSprintId, setFilterSprintId] = useState("");
  const [search, setSearch] = useState("");
  const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());
  const [historyJiraKey, setHistoryJiraKey] = useState<string | null>(null);
  const [sprintCatalog, setSprintCatalog] = useState<{ id: number; label: string }[]>([]);

  const patchStoryInList = useCallback((record: JiraStoryRecord) => {
    setAllData((prev) => sortStoryVersions(
      dedupeLatestRecords([
        ...prev.filter((r) => r.jira_key !== record.jira_key),
        record,
      ]),
    ));
  }, []);

  const titleSpotlight = useTitleSpotlight({
    onPersistTitle: async (row, title) => {
      const payload = { ...recordToSavePayload(row, row.project_key), title };
      const saved = await updateStory(payload);
      patchStoryInList(apiStoryToRecord(saved));
    },
    onRegenerateTitle: async (row) => {
      const result = await regenerateStoryTitle(row.jira_key, row.snapshot_date);
      return result.suggestions;
    },
  });
  const tableScrollRef = useRef<HTMLDivElement>(null);

  // Track filter options + sprint catalog (latest snapshot per jira_key only).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const fullLatest = await fetchAllStories({ latestOnly: true });
        if (cancelled) return;
        const catalog = storiesToLatestRecords(fullLatest.stories);
        setDbTrackList(tracksFromStoryRecords(catalog));
        const sprintMap = new Map<number, string>();
        for (const s of catalog) {
          if (s.sprint_id != null && s.sprint_name) {
            sprintMap.set(s.sprint_id, s.sprint_name);
          }
        }
        setSprintCatalog(
          [...sprintMap.entries()].map(([id, label]) => ({ id, label })).sort((a, b) => a.label.localeCompare(b.label)),
        );
      } catch {
        if (!cancelled) setDbTrackList([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setFetchError("");
      try {
        const versionOpts = { latestOnly: true as const };
        let response = await fetchAllStories(versionOpts);
        if (filterSprintId) {
          response = await fetchStoriesBySprint(Number(filterSprintId), versionOpts);
        } else if (filterAssignee) {
          response = await fetchStoriesByAssignee(filterAssignee, versionOpts);
        } else if (filterTrack) {
          const tracksForFilter = enrichTracksWithCatalog(
            dbTrackList.length > 0 ? dbTrackList : catalogToImportedTracks(trackCatalog),
            trackCatalog,
          );
          const pid = projectIdForTrackName(filterTrack, tracksForFilter, trackCatalog);
          if (pid) response = await fetchStoriesByTrack(pid, versionOpts);
        }

        if (!cancelled) {
          setAllData(sortStoryVersions(storiesToLatestRecords(response.stories)));
        }
      } catch (err) {
        if (!cancelled) {
          setFetchError(err instanceof Error ? err.message : "Failed to load stories");
          setAllData([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [filterTrack, filterAssignee, filterSprintId, dbTrackList, trackCatalog]);

  const reporteeMap = useMemo(() => buildReporteeMap(uiTracks, allData as JiraIssue[]), [uiTracks, allData]);

  const assignees = [...new Set(allData.map((d) => d.assignee))].filter(Boolean);

  const filtered = sortStoryVersions(allData.filter((d) => {
    if (filterTrack && !filterSprintId && !filterAssignee) {
      const codes = new Set(
        (uiTracks.find((x) => x.name === filterTrack)?.codes ?? []).map((c) => c.toUpperCase()),
      );
      if (codes.size > 0 && !codes.has((d.project_key ?? "").toUpperCase())) return false;
    }
    if (filterAssignee && filterTrack) {
      const codes = new Set(
        (uiTracks.find((x) => x.name === filterTrack)?.codes ?? []).map((c) => c.toUpperCase()),
      );
      if (codes.size > 0 && !codes.has((d.project_key ?? "").toUpperCase())) return false;
    }
    if (filterSprintId && filterTrack) {
      const codes = new Set(
        (uiTracks.find((x) => x.name === filterTrack)?.codes ?? []).map((c) => c.toUpperCase()),
      );
      if (codes.size > 0 && !codes.has((d.project_key ?? "").toUpperCase())) return false;
    }
    if (search) {
      const q = search.toLowerCase();
      if (
        !d.jira_key?.toLowerCase().includes(q) &&
        !d.title?.toLowerCase().includes(q) &&
        !d.assignee?.toLowerCase().includes(q) &&
        !d.description?.toLowerCase().includes(q)
      ) return false;
    }
    return true;
  }));

  const totalDone = filtered.filter((d) => normalizeStatus(d.status) === "Done").length;
  const totalInProgress = filtered.filter((d) => normalizeStatus(d.status) === "In Progress").length;
  const totalTodo = filtered.filter((d) => normalizeStatus(d.status) === "To Do").length;
  const overallPct = statusCompletionPct(filtered as JiraIssue[]);

  const toggleRow = (key: string) => {
    const s = new Set(selectedRows);
    s.has(key) ? s.delete(key) : s.add(key);
    setSelectedRows(s);
  };

  const clearFilters = () => {
    setFilterTrack("");
    setFilterAssignee("");
    setFilterSprintId("");
    setSearch("");
  };

  return (
    <div className="flex flex-col h-full relative">
      {historyJiraKey && (
        <StoryHistoryModal
          jiraKey={historyJiraKey}
          onClose={() => setHistoryJiraKey(null)}
        />
      )}
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 bg-white">
        <h1 className="text-base font-semibold text-gray-800">Story Board</h1>
      </div>

      {fetchError ? (
        <div className="px-6 py-2 bg-red-50 border-b border-red-100 text-xs text-red-600">
          Could not load stories: {fetchError}
        </div>
      ) : null}

      <div className="flex-1 overflow-auto">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 px-6 py-4">
          {[
            { label: "TOTAL TICKETS", value: filtered.length, color: "text-gray-800" },
            { label: "TO DO", value: totalTodo, color: "text-gray-600" },
            { label: "IN PROGRESS", value: totalInProgress, color: "text-blue-600" },
            { label: "DONE", value: totalDone, color: "text-green-600" },
            { label: "% COMPLETE", value: `${overallPct}%`, color: "text-brand-red" },
          ].map((s) => (
            <div key={s.label} className="bg-white border border-gray-200 rounded-xl px-5 py-4">
              <p className="text-xs font-semibold text-gray-400 mb-1">{s.label}</p>
              <p className={`text-3xl font-bold ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="mx-6 mb-4 bg-white border border-gray-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <SlidersHorizontal className="w-4 h-4 text-gray-500" />
            <span className="text-sm font-semibold text-gray-700">FILTERS</span>
            {(filterTrack || filterAssignee || filterSprintId || search) && (
              <button onClick={clearFilters} className="ml-auto text-xs text-brand-red hover:text-brand-red-dark">Clear all</button>
            )}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">TRACK</label>
              <Select value={filterTrack} onChange={setFilterTrack} options={trackOptions} placeholder="All Tracks" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">ASSIGNEE</label>
              <Select value={filterAssignee} onChange={setFilterAssignee} options={assignees} placeholder="All Assignees" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">SPRINT</label>
              <IdSelect value={filterSprintId} onChange={setFilterSprintId} options={sprintCatalog} placeholder="All Sprints" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">SEARCH</label>
              <div className="relative">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                <input value={search} onChange={(e) => setSearch(e.target.value)}
                  placeholder="Key, title, assignee…"
                  className="w-full pl-7 pr-3 py-1.5 border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-brand-red/40" />
              </div>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="mx-6 mb-6 bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div ref={tableScrollRef} className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="w-10 px-3 py-3">
                    <input type="checkbox" className="rounded"
                      onChange={(e) => {
                        if (e.target.checked) setSelectedRows(new Set(filtered.map((d) => storyRowKey(d))));
                        else setSelectedRows(new Set());
                      }} />
                  </th>
                  {["Jira Key", "Snapshot", "Title", "Track", "Sprint", "Date Assigned", "Status", "Story Points", "% Complete", "Assignee", "Reportee"].map((h) => (
                    <th key={h} className="px-3 py-3 text-left text-gray-500 font-semibold whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr><td colSpan={12} className="px-3 py-12 text-center text-gray-400">Loading stories from database…</td></tr>
                )}
                {!loading && filtered.map((row, i) => {
                  const pct = completionPct(row.status);
                  const rowKey = storyRowKey(row);
                  const expanded = titleSpotlight.isExpanded(row.jira_key);
                  return (
                    <Fragment key={rowKey}>
                    <tr
                      className={`border-b border-gray-100 hover:bg-brand-red/10 ${selectedRows.has(rowKey) ? "bg-brand-red/10" : expanded ? "bg-brand-red/10" : i % 2 === 0 ? "bg-white" : "bg-gray-50/30"}`}>
                      <td className="px-3 py-2.5">
                        <input type="checkbox" checked={selectedRows.has(rowKey)} onChange={() => toggleRow(rowKey)} className="rounded" />
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <button
                          type="button"
                          disabled={row.isDraft || !row.jira_key}
                          onClick={() => setHistoryJiraKey(row.jira_key)}
                          className="text-xs text-brand-red hover:text-brand-red hover:underline disabled:text-gray-400 disabled:no-underline disabled:cursor-default"
                          title="View version history"
                        >
                          {row.jira_key}
                        </button>
                      </td>
                      <td className="px-3 py-2.5 text-gray-500 whitespace-nowrap">{formatSnapshotDate(row)}</td>
                      <td className="px-3 py-2.5 max-w-xs">
                        <ClickableSummaryCell
                          text={titleSpotlight.displayTitle(row)}
                          expanded={expanded}
                          onClick={() => titleSpotlight.toggleForRow(row)}
                        />
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <span className="font-semibold text-gray-700">{displayTrackName(row.project_key, uiTracks)}</span>
                        <span className="text-gray-400 ml-1">({row.project_key})</span>
                      </td>
                      <td className="px-3 py-2.5 text-gray-600 whitespace-nowrap text-xs">{row.sprint_name}</td>
                      <td className="px-3 py-2.5 text-gray-600 whitespace-nowrap">{formatAssignedDate(row)}</td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <StatusBadge status={row.status} />
                      </td>
                      <td className="px-3 py-2.5 text-center">
                        {row.story_points != null
                          ? <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-brand-red/10 text-brand-red font-bold text-xs">{row.story_points}</span>
                          : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-2 min-w-20">
                          <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                            <div className={`h-1.5 rounded-full ${pct === 100 ? "bg-green-500" : pct > 0 ? "bg-brand-red/100" : "bg-gray-200"}`} style={{ width: `${pct}%` }} />
                          </div>
                          <span className={`text-xs font-semibold w-8 text-right ${pct === 100 ? "text-green-600" : pct > 0 ? "text-blue-600" : "text-gray-400"}`}>{pct}%</span>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 text-gray-700 whitespace-nowrap">{row.assignee}</td>
                      <td className="px-3 py-2.5 text-gray-600 whitespace-nowrap">
                        {getReporteeForAssignee(row.assignee, reporteeMap)}
                      </td>
                    </tr>
                    {expanded && (
                      <InlineSummaryExpansionRow colSpan={12} scrollRef={tableScrollRef} horizontalPad="px-3">
                        <InlineSummaryEditor
                          summary={titleSpotlight.displayTitle(row)}
                          contextLabel={row.jira_key}
                          fieldLabel="Title"
                          onClose={titleSpotlight.close}
                          onCommit={(text) => { void titleSpotlight.commitTitle(text); }}
                          onClearSuggestions={titleSpotlight.clearSuggestions}
                          onAiGenerate={() => { void titleSpotlight.handleAiGenerate(); }}
                          suggestions={titleSpotlight.suggestions}
                          isGenerating={titleSpotlight.isGenerating}
                          highlightIdx={titleSpotlight.highlightIdx}
                          onHighlightChange={titleSpotlight.setHighlightIdx}
                        />
                      </InlineSummaryExpansionRow>
                    )}
                    </Fragment>
                  );
                })}
                {!loading && filtered.length === 0 && (
                  <tr><td colSpan={12} className="px-3 py-12 text-center text-gray-400">No tickets match the current filters</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}


// ── HEB Logo SVG ────────────────────────────────────────────────
// App palette tokens used in slides
const SLIDE_ACCENT = "#d3072a";
const SLIDE_HEADER_BG = "#202020";
const SLIDE_LIGHT_BG = "#f5f6ff";    // very light indigo tint for section bodies

// ── Inline editable text ─────────────────────────────────────────
function EditableText({
  value, onChange, className, multiline, placeholder,
}: { value: string; onChange: (v: string) => void; className?: string; multiline?: boolean; placeholder?: string }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  if (editing) {
    if (multiline) {
      return (
        <textarea
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => { onChange(draft); setEditing(false); }}
          className={`bg-yellow-50 border border-yellow-400 rounded px-1 py-0.5 w-full resize-none focus:outline-none ${className}`}
          rows={2}
        />
      );
    }
    return (
      <input
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => { onChange(draft); setEditing(false); }}
        onKeyDown={(e) => { if (e.key === "Enter") { onChange(draft); setEditing(false); } }}
        className={`bg-yellow-50 border border-yellow-400 rounded px-1 py-0.5 w-full focus:outline-none ${className}`}
      />
    );
  }
  return (
    <span
      onClick={() => { setDraft(value); setEditing(true); }}
      className={`cursor-text hover:bg-yellow-50 hover:outline hover:outline-1 hover:outline-yellow-300 rounded px-0.5 transition-colors ${className}`}
      title="Click to edit"
    >
      {value || <span className="text-gray-300 italic">{placeholder ?? "Click to edit"}</span>}
    </span>
  );
}

// ── Index Slide ──────────────────────────────────────────────────
function IndexSlide({ slides }: { slides: WsrSlide[] }) {
  const seenTracks = new Set<string>();
  const indexEntries: { slideNum: number; label: string; tech: string; trackId: string }[] = [];
  for (const s of slides.filter((s) => s.type === "track")) {
    if (!s.trackId || seenTracks.has(s.trackId)) continue;
    seenTracks.add(s.trackId);
    const track = WSR_TRACKS.find((t) => t.id === s.trackId)!;
    indexEntries.push({ slideNum: s.slideNum, label: track.fullName, tech: track.tech, trackId: track.id });
  }

  // Accent colours per track (cycling through a harmonious palette)
  const TRACK_COLORS = [
    { bg: "#fde8ec", border: "#d3072a", num: "#d3072a" },
    { bg: "#f0fdf4", border: "#22c55e", num: "#15803d" },
    { bg: "#faf5ff", border: "#a855f7", num: "#7e22ce" },
    { bg: "#fff7ed", border: "#f97316", num: "#c2410c" },
    { bg: "#eff6ff", border: "#3b82f6", num: "#1d4ed8" },
    { bg: "#fdf2f8", border: "#ec4899", num: "#9d174d" },
    { bg: "#f0fdfa", border: "#14b8a6", num: "#0f766e" },
    { bg: "#fefce8", border: "#eab308", num: "#854d0e" },
  ];

  return (
    <div className="w-full h-full flex flex-col" style={{ fontFamily: "Inter, sans-serif", background: "#f8f9fc" }}>
      {/* Header band */}
      <div className="flex items-center justify-between px-8 py-5" style={{ background: SLIDE_HEADER_BG }}>
        <div>
          <p className="text-white/50 text-xs font-medium uppercase tracking-widest mb-0.5">Weekly Status Report</p>
          <h1 className="text-white text-xl font-bold tracking-tight">Track Index</h1>
        </div>
        <div className="flex items-center gap-2 bg-white/10 rounded-lg px-3 py-1.5">
          <div className="w-2 h-2 rounded-full bg-brand-red/70" />
          <span className="text-white/70 text-xs font-medium">Week 24 · Jun 2026</span>
        </div>
      </div>

      {/* Subtitle bar */}
      <div className="px-8 py-2.5 bg-white border-b border-gray-100 flex items-center gap-2">
        <span className="text-xs text-gray-400">Navigate to any track's section using the slide numbers below</span>
      </div>

      {/* Grid */}
      <div className="flex-1 px-8 py-6 flex items-center">
        <div className="grid grid-cols-4 gap-4 w-full">
          {indexEntries.map((entry, i) => {
            const colors = TRACK_COLORS[i % TRACK_COLORS.length];
            return (
              <div
                key={entry.trackId}
                className="rounded-xl border-2 flex flex-col overflow-hidden"
                style={{ background: colors.bg, borderColor: colors.border }}
              >
                {/* Slide number badge */}
                <div className="flex items-center justify-between px-3 pt-3 pb-1">
                  <span
                    className="text-3xl font-black leading-none"
                    style={{ color: colors.num }}
                  >
                    {String(entry.slideNum).padStart(2, "0")}
                  </span>
                  <div
                    className="w-2 h-2 rounded-full opacity-60"
                    style={{ background: colors.border }}
                  />
                </div>
                {/* Track info */}
                <div className="px-3 pb-3 flex-1 flex flex-col justify-end">
                  <p className="text-xs font-bold text-gray-800 leading-snug">{entry.label}</p>
                  {entry.tech && (
                    <p className="text-xs text-gray-400 mt-0.5 leading-tight">{entry.tech}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="px-8 py-3 border-t border-gray-200 bg-white flex items-center justify-between">
        <span className="text-xs text-gray-400">{indexEntries.length} tracks · {slides.length - 1} slides total</span>
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-brand-red/70" />
          <div className="w-1.5 h-1.5 rounded-full bg-brand-orange/40" />
          <div className="w-1.5 h-1.5 rounded-full bg-brand-red/30" />
        </div>
      </div>
    </div>
  );
}

// ── Track Slide ──────────────────────────────────────────────────
function TrackSlide({
  track, sprint, edits, onEdit,
}: {
  track: WsrTrack;
  sprint: WsrSprint;
  edits: Record<string, string>;
  onEdit: (key: string, val: string) => void;
}) {
  const done = sprint.stories.filter((s) => s.status === "Done");
  const inProgress = sprint.stories.filter((s) => s.status === "In Progress" || s.status === "To Do");

  const get = (k: string, fallback: string) => edits[k] ?? fallback;
  const set = (k: string) => (v: string) => onEdit(k, v);
  const pfx = `${track.id}-${sprint.id}`;

  return (
    <div className="w-full h-full flex flex-col overflow-hidden bg-[#f8f9fc]" style={{ fontFamily: "Inter, sans-serif", fontSize: "11px" }}>
      {/* Header band – matches app sidebar navy */}
      <div className="flex items-center justify-between px-5 py-3 flex-shrink-0" style={{ background: SLIDE_HEADER_BG }}>
        <div className="min-w-0">
          <EditableText
            value={get(`${pfx}-title`, `Delivery Status — ${track.fullName}`)}
            onChange={set(`${pfx}-title`)}
            className="text-sm font-bold text-white block"
          />
          <EditableText
            value={get(`${pfx}-subtitle`, `Week ${sprint.start} – ${sprint.end}, 2026  ·  Tech: ${track.tech}`)}
            onChange={set(`${pfx}-subtitle`)}
            className="text-xs text-white/50 mt-0.5 block"
          />
        </div>
        {/* Week badge */}
        <div className="flex-shrink-0 ml-4 bg-white/10 rounded-lg px-3 py-1.5 text-white/70 text-xs font-medium whitespace-nowrap">
          {sprint.start} – {sprint.end}
        </div>
      </div>

      {/* Thin accent bar */}
      <div className="h-0.5 flex-shrink-0" style={{ background: SLIDE_ACCENT }} />

      <div className="flex flex-1 min-h-0 p-3 gap-3">
        {/* Main content column */}
        <div className="flex-1 flex flex-col gap-2.5 min-w-0 overflow-hidden">

          {/* Sprint summary pill row */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-gray-600">Sprint:</span>
            <span className="text-xs font-bold text-gray-800">{sprint.name}</span>
            <span className="text-xs text-gray-400">·</span>
            {[
              { label: `${sprint.stories.length} Total`, color: "bg-gray-200 text-gray-700" },
              { label: `${done.length} Done`, color: "bg-green-100 text-green-700" },
              { label: `${inProgress.length} In Progress`, color: "bg-blue-100 text-blue-700" },
            ].map((chip) => (
              <span key={chip.label} className={`px-2 py-0.5 rounded-full text-xs font-semibold ${chip.color}`}>{chip.label}</span>
            ))}
          </div>

          {/* Highlights */}
          <div className="rounded-lg overflow-hidden border border-brand-red/20">
            <div className="flex items-center gap-2 px-3 py-1.5 text-white text-xs font-semibold" style={{ background: SLIDE_ACCENT }}>
              <svg className="w-3 h-3 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              Highlights
            </div>
            <div className="px-3 py-2 space-y-2" style={{ background: SLIDE_LIGHT_BG }}>
              {done.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 mb-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0" />
                    <span className="text-xs font-bold text-gray-700">Completed this week — {done.length} {done.length === 1 ? "story" : "stories"}</span>
                  </div>
                  {done.map((s) => (
                    <div key={s.key} className="flex items-start gap-2 ml-3 text-gray-600 leading-snug py-0.5">
                      <span className="flex-shrink-0 text-gray-300 mt-0.5">›</span>
                      <EditableText value={get(`${pfx}-done-${s.key}`, s.summary)} onChange={set(`${pfx}-done-${s.key}`)} className="text-xs text-gray-600" multiline />
                    </div>
                  ))}
                </div>
              )}
              {inProgress.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 mb-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-brand-red/100 flex-shrink-0" />
                    <span className="text-xs font-bold text-gray-700">In progress — {inProgress.length} {inProgress.length === 1 ? "story" : "stories"}</span>
                  </div>
                  {inProgress.map((s) => (
                    <div key={s.key} className="flex items-start gap-2 ml-3 text-gray-600 leading-snug py-0.5">
                      <span className="flex-shrink-0 text-gray-300 mt-0.5">›</span>
                      <EditableText value={get(`${pfx}-ip-${s.key}`, s.summary)} onChange={set(`${pfx}-ip-${s.key}`)} className="text-xs text-gray-600" multiline />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Key activities next week */}
          <div className="rounded-lg overflow-hidden border border-brand-red/20">
            <div className="flex items-center gap-2 px-3 py-1.5 text-white text-xs font-semibold" style={{ background: "#d94809" }}>
              <svg className="w-3 h-3 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 9l3 3-3 3m-5-3h8" /></svg>
              Key Activities for Next Week
            </div>
            <div className="px-3 py-2 space-y-1" style={{ background: SLIDE_LIGHT_BG }}>
              {sprint.nextWeek.map((item, i) => (
                <div key={i} className="flex items-start gap-2 text-gray-600 leading-snug">
                  <span className="w-4 h-4 rounded-full bg-brand-red/10 text-brand-red flex-shrink-0 flex items-center justify-center text-xs font-bold mt-0.5">{i + 1}</span>
                  <EditableText value={get(`${pfx}-nw-${i}`, item)} onChange={set(`${pfx}-nw-${i}`)} className="text-xs text-gray-600" multiline />
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right sidebar */}
        <div className="w-32 flex-shrink-0 flex flex-col gap-2">
          {/* Overall status */}
          <div className="rounded-lg overflow-hidden border border-brand-red/20">
            <div className="text-center text-white text-xs font-semibold py-1" style={{ background: SLIDE_ACCENT }}>Overall Status</div>
            <div className="grid grid-cols-2 divide-x divide-gray-200">
              <div className="text-center py-1 text-xs text-gray-400 bg-gray-50">Last wk</div>
              <div className="text-center py-1 text-xs text-gray-400 bg-gray-50">This wk</div>
              <div className="py-2 flex items-center justify-center bg-green-50">
                <div className="w-4 h-4 rounded-full bg-green-400" />
              </div>
              <div className="py-2 flex items-center justify-center bg-green-50">
                <div className="w-4 h-4 rounded-full bg-green-500" />
              </div>
            </div>
          </div>

          {/* Sprint stats */}
          <div className="rounded-lg overflow-hidden border border-brand-red/20">
            <div className="text-center text-white text-xs font-semibold py-1" style={{ background: SLIDE_HEADER_BG }}>Sprint Stats</div>
            <div className="p-2 space-y-1.5 bg-gray-50">
              {[
                { label: "Total", val: sprint.stories.length, tw: "bg-gray-500" },
                { label: "Done", val: done.length, tw: "bg-green-500" },
                { label: "In Progress", val: inProgress.filter((s) => s.status === "In Progress").length, tw: "bg-brand-red/100" },
                { label: "To Do", val: inProgress.filter((s) => s.status === "To Do").length, tw: "bg-gray-300" },
              ].map((row) => (
                <div key={row.label} className="flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-sm flex-shrink-0 ${row.tw}`} />
                  <span className="text-xs text-gray-500 flex-1 truncate">{row.label}</span>
                  <span className="text-xs font-bold text-gray-800">{row.val}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Team */}
          <div className="rounded-lg overflow-hidden border border-brand-red/20">
            <div className="text-center text-white text-xs font-semibold py-1" style={{ background: SLIDE_HEADER_BG }}>Team</div>
            <div className="p-2 space-y-1 bg-gray-50">
              {[...new Set(sprint.stories.map((s) => s.assignee))].map((name) => (
                <div key={name} className="flex items-center gap-1.5">
                  <div className="w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center text-white text-xs font-bold" style={{ background: SLIDE_ACCENT }}>
                    {name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                  </div>
                  <span className="text-xs text-gray-600 truncate">{name.split(" ")[0]}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Shared WSR Slide Viewer ───────────────────────────────────────
function WSRSlideViewer({
  edits, onEdit, activeSlide, onSlideChange, footerSlot,
}: {
  edits: Record<string, string>;
  onEdit: (k: string, v: string) => void;
  activeSlide: number;
  onSlideChange: (n: number) => void;
  footerSlot?: React.ReactNode;
}) {
  const slides = buildWsrSlides();
  const current = slides.find((s) => s.slideNum === activeSlide)!;
  const track = current.type === "track" ? WSR_TRACKS.find((t) => t.id === current.trackId) : null;
  const sprint = track ? track.sprints.find((sp) => sp.id === current.sprintId) : null;

  return (
    <div className="flex h-full min-h-0">
      {/* Slide navigator */}
      <div className="w-52 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <div className="px-3 py-3 border-b border-gray-100 bg-gray-50">
          <p className="text-xs font-bold text-gray-700 uppercase tracking-wide">Slides</p>
          <p className="text-xs text-gray-400 mt-0.5">{slides.length} slides · {WSR_TRACKS.length} tracks</p>
        </div>
        <div className="flex-1 overflow-y-auto py-1">
          {slides.map((slide) => (
            <button
              key={slide.slideNum}
              onClick={() => onSlideChange(slide.slideNum)}
              className={`w-full flex items-start gap-2.5 px-3 py-2 text-left transition-colors hover:bg-brand-red/10 ${activeSlide === slide.slideNum ? "bg-brand-red/10 border-l-2 border-brand-red" : "border-l-2 border-transparent"}`}
            >
              <span className={`text-xs font-bold flex-shrink-0 mt-0.5 w-5 text-right ${activeSlide === slide.slideNum ? "text-brand-red" : "text-gray-400"}`}>
                {String(slide.slideNum).padStart(2, "0")}
              </span>
              <span className={`text-xs leading-snug ${activeSlide === slide.slideNum ? "text-brand-red font-semibold" : "text-gray-600"}`}>
                {slide.label}
              </span>
            </button>
          ))}
        </div>
        {footerSlot && <div className="p-3 border-t border-gray-200">{footerSlot}</div>}
      </div>

      {/* Canvas */}
      <div className="flex-1 flex flex-col min-w-0 bg-gray-200">
        <div className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200">
          <div className="flex items-center gap-2">
            <button onClick={() => onSlideChange(Math.max(1, activeSlide - 1))} disabled={activeSlide === 1}
              className="px-3 py-1.5 text-xs border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-40 font-medium">← Prev</button>
            <span className="text-xs text-gray-500 font-medium">Slide {activeSlide} / {slides.length}</span>
            <button onClick={() => onSlideChange(Math.min(slides.length, activeSlide + 1))} disabled={activeSlide === slides.length}
              className="px-3 py-1.5 text-xs border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-40 font-medium">Next →</button>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 border border-amber-200 px-2 py-1 rounded-md">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
            Click any text to edit inline
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center p-6 overflow-auto">
          <div className="bg-white shadow-2xl rounded overflow-hidden" style={{ width: "min(900px, calc(100% - 2rem))", aspectRatio: "16/9" }}>
            {current.type === "index"
              ? <IndexSlide slides={slides} />
              : track && sprint
                ? <TrackSlide track={track} sprint={sprint} edits={edits} onEdit={onEdit} />
                : null}
          </div>
        </div>
        <div className="px-4 py-2 bg-white border-t border-gray-200 flex items-center gap-2">
          <span className="text-xs font-bold text-gray-400">#{activeSlide}</span>
          <span className="text-xs text-gray-600 font-medium">{current.label}</span>
          {current.type === "track" && track && <span className="text-xs text-gray-400">· {track.tech}</span>}
        </div>
      </div>
    </div>
  );
}

// ── Week Picker Calendar Popover ──────────────────────────────────
const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const DAY_NAMES = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];

function WeekPickerPopover({
  selectedMonday,
  onChange,
  maxDate,
  placeholder = "Select a week",
}: {
  selectedMonday: Date | null;
  onChange: (monday: Date) => void;
  maxDate?: Date;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [viewDate, setViewDate] = useState(() => selectedMonday ?? new Date());
  const [hoverMonday, setHoverMonday] = useState<Date | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setHoverMonday(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();

  // Build calendar grid — rows of 7 days starting Monday
  const firstOfMonth = new Date(year, month, 1);
  const startOffset = (firstOfMonth.getDay() + 6) % 7; // Mon=0 … Sun=6
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const weeks: (Date | null)[][] = [];
  let cursor = 1 - startOffset;
  while (cursor <= daysInMonth) {
    const row: (Date | null)[] = [];
    for (let d = 0; d < 7; d++, cursor++) {
      row.push(cursor >= 1 && cursor <= daysInMonth ? new Date(year, month, cursor) : null);
    }
    weeks.push(row);
  }

  const sameDay = (a: Date | null, b: Date | null) =>
    !!a && !!b && a.toDateString() === b.toDateString();

  const inRange = (d: Date | null, monday: Date | null): boolean => {
    if (!d || !monday) return false;
    const fri = getFridayOf(monday);
    return d >= monday && d <= fri;
  };

  const isDisabled = (d: Date | null) => {
    if (!d) return true;
    if (maxDate) {
      const dayOnly = new Date(d); dayOnly.setHours(0,0,0,0);
      const maxOnly = new Date(maxDate); maxOnly.setHours(0,0,0,0);
      return dayOnly > maxOnly;
    }
    return false;
  };

  const handleRowClick = (row: (Date | null)[]) => {
    const firstValid = row.find((d) => d && !isDisabled(d));
    if (!firstValid) return;
    const monday = getMondayOf(firstValid);
    onChange(monday);
    setOpen(false);
    setHoverMonday(null);
  };

  const handleRowHover = (row: (Date | null)[]) => {
    const firstValid = row.find((d) => d && !isDisabled(d));
    setHoverMonday(firstValid ? getMondayOf(firstValid) : null);
  };

  const label = selectedMonday
    ? `${fmtDateShort(selectedMonday)}  –  ${fmtDateShort(getFridayOf(selectedMonday))}`
    : placeholder;

  return (
    <div className="relative" ref={containerRef}>
      {/* Trigger */}
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-all ${
          open
            ? "border-brand-red/50 ring-2 ring-brand-red/20 bg-brand-red/10 text-brand-red"
            : selectedMonday
              ? "border-brand-red/40 bg-white text-brand-red hover:border-brand-red/50"
              : "border-gray-200 bg-white text-gray-400 hover:border-brand-red/40 hover:text-gray-600"
        }`}
      >
        <Calendar className="w-4 h-4 flex-shrink-0 text-brand-red" />
        <span className="whitespace-nowrap">{label}</span>
        <ChevronDown className={`w-3.5 h-3.5 flex-shrink-0 text-gray-400 transition-transform ml-0.5 ${open ? "rotate-180" : ""}`} />
      </button>

      {/* Popover */}
      {open && (
        <div className="absolute top-full mt-2 left-0 z-50 bg-white rounded-2xl shadow-2xl border border-gray-200 p-4 select-none" style={{ width: 288 }}>
          {/* Month navigation */}
          <div className="flex items-center justify-between mb-3">
            <button
              onClick={() => setViewDate(new Date(year, month - 1, 1))}
              className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-gray-100 text-gray-500 font-bold text-base transition-colors"
            >‹</button>
            <span className="text-sm font-semibold text-gray-800">{MONTH_NAMES[month]} {year}</span>
            <button
              onClick={() => setViewDate(new Date(year, month + 1, 1))}
              className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-gray-100 text-gray-500 font-bold text-base transition-colors"
            >›</button>
          </div>

          {/* Day headers */}
          <div className="grid grid-cols-7 mb-1">
            {DAY_NAMES.map((d) => (
              <div key={d} className={`text-center text-xs font-semibold py-1 ${d === "Sat" || d === "Sun" ? "text-gray-300" : "text-gray-400"}`}>
                {d}
              </div>
            ))}
          </div>

          {/* Week rows */}
          <div className="space-y-0.5">
            {weeks.map((row, wi) => {
              const rowHasValid = row.some((d) => d && !isDisabled(d));
              return (
                <div
                  key={wi}
                  className={`grid grid-cols-7 rounded-xl overflow-hidden ${rowHasValid ? "cursor-pointer" : ""}`}
                  onMouseEnter={() => rowHasValid && handleRowHover(row)}
                  onMouseLeave={() => setHoverMonday(null)}
                  onClick={() => handleRowClick(row)}
                >
                  {row.map((d, di) => {
                    const weekend = di >= 5; // Sat/Sun cols
                    const disabled = isDisabled(d);
                    const inSel = inRange(d, selectedMonday);
                    const inHov = inRange(d, hoverMonday);
                    const isSelMonday = d && selectedMonday && sameDay(d, selectedMonday);
                    const isSelFriday = d && selectedMonday && sameDay(d, getFridayOf(selectedMonday));

                    return (
                      <div
                        key={di}
                        className={[
                          "text-center py-2 text-xs font-medium transition-colors",
                          !d ? "text-transparent" : "",
                          disabled && d ? "text-gray-200 cursor-not-allowed" : "",
                          weekend && d && !disabled ? "text-gray-300" : "",
                          !weekend && d && !disabled && !inSel && !inHov ? "text-gray-700" : "",
                          inSel && !weekend ? "bg-brand-red text-white" : "",
                          inHov && !inSel && !weekend ? "bg-brand-red/10 text-brand-red" : "",
                          isSelMonday ? "rounded-l-full" : "",
                          isSelFriday ? "rounded-r-full" : "",
                        ].filter(Boolean).join(" ")}
                      >
                        {d?.getDate() ?? ""}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>

          {/* Selected week label */}
          {selectedMonday && (
            <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-center font-semibold text-brand-red">
              {fmtDateShort(selectedMonday)} – {fmtDateShort(getFridayOf(selectedMonday))}
            </div>
          )}

          {/* Hint */}
          <p className="text-xs text-center text-gray-400 mt-1">Click any row to select that week (Mon – Fri)</p>
        </div>
      )}
    </div>
  );
}

// ── Plain Day Picker Calendar Popover ────────────────────────────
function DatePickerPopover({
  selected,
  onChange,
  placeholder = "Pick a date",
  align = "right",
}: {
  selected: Date | null;
  onChange: (d: Date) => void;
  placeholder?: string;
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const [viewDate, setViewDate] = useState(() => selected ?? new Date());
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const firstOfMonth = new Date(year, month, 1);
  const startOffset = (firstOfMonth.getDay() + 6) % 7; // Mon=0
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells: (Date | null)[] = [];
  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));

  const sameDay = (a: Date | null, b: Date | null) =>
    !!a && !!b && a.toDateString() === b.toDateString();

  const label = selected
    ? selected.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })
    : placeholder;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-all ${
          open
            ? "border-brand-red/50 ring-2 ring-brand-red/20 bg-brand-red/10 text-brand-red"
            : selected
              ? "border-brand-red/40 bg-white text-brand-red hover:border-brand-red/50"
              : "border-gray-200 bg-white text-gray-400 hover:border-brand-red/40 hover:text-gray-600"
        }`}
      >
        <Calendar className="w-4 h-4 flex-shrink-0 text-brand-red" />
        <span className="whitespace-nowrap">{label}</span>
        <ChevronDown className={`w-3.5 h-3.5 flex-shrink-0 text-gray-400 ml-0.5 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className={`absolute top-full mt-2 z-50 bg-white rounded-2xl shadow-2xl border border-gray-200 p-4 select-none ${align === "right" ? "right-0" : "left-0"}`} style={{ width: 272 }}>
          {/* Month nav */}
          <div className="flex items-center justify-between mb-3">
            <button onClick={() => setViewDate(new Date(year, month - 1, 1))}
              className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-gray-100 text-gray-500 font-bold text-base">‹</button>
            <span className="text-sm font-semibold text-gray-800">{MONTH_NAMES[month]} {year}</span>
            <button onClick={() => setViewDate(new Date(year, month + 1, 1))}
              className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-gray-100 text-gray-500 font-bold text-base">›</button>
          </div>

          {/* Day headers */}
          <div className="grid grid-cols-7 mb-1">
            {DAY_NAMES.map((d) => (
              <div key={d} className={`text-center text-xs font-semibold py-1 ${d === "Sat" || d === "Sun" ? "text-gray-300" : "text-gray-400"}`}>{d}</div>
            ))}
          </div>

          {/* Day grid */}
          <div className="grid grid-cols-7 gap-y-0.5">
            {cells.map((d, i) => {
              if (!d) return <div key={i} />;
              const isSelected = sameDay(d, selected);
              const isWeekend = d.getDay() === 0 || d.getDay() === 6;
              return (
                <button
                  key={i}
                  onClick={() => { onChange(d); setOpen(false); }}
                  className={[
                    "h-8 w-full rounded-full text-xs font-medium transition-colors",
                    isSelected ? "bg-brand-red text-white" : "",
                    !isSelected && isWeekend ? "text-gray-300 hover:bg-gray-50" : "",
                    !isSelected && !isWeekend ? "text-gray-700 hover:bg-brand-red/10 hover:text-brand-red" : "",
                  ].filter(Boolean).join(" ")}
                >
                  {d.getDate()}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Generate WSR Page ─────────────────────────────────────────────
type GenerateWsrStep = "template" | "generate";

function GenerateWSRPage() {
  const today = new Date();
  const [weekStart, setWeekStart] = useState<Date>(() => getMondayOf(today));
  const [step, setStep] = useState<GenerateWsrStep>("template");
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [confirmedTemplate, setConfirmedTemplate] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const weekEnd = getFridayOf(weekStart);

  const handleProceed = useCallback((id: string, item: { original_filename: string }) => {
    setConfirmedTemplate({ id, name: item.original_filename });
    setStep("generate");
  }, []);

  const handleTemplateSelect = useCallback((id: string | null) => {
    setSelectedTemplateId(id);
  }, []);

  const weekHeader = (
    <div className="flex items-center gap-4 px-6 py-3 bg-white border-b border-gray-200 flex-shrink-0">
      <span className="text-sm font-semibold text-gray-700 whitespace-nowrap">Report Week:</span>
      <WeekPickerPopover
        selectedMonday={weekStart}
        onChange={setWeekStart}
        maxDate={today}
      />
      <span className="text-xs text-gray-400">
        {fmtDate(weekStart)} – {fmtDate(weekEnd)}
      </span>
    </div>
  );

  if (step === "template") {
    return (
      <div className="flex flex-col h-full min-h-0">
        {weekHeader}
        <WSRTemplateSelector
          selectedId={selectedTemplateId}
          onSelectedIdChange={handleTemplateSelect}
          onProceed={handleProceed}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {weekHeader}
      <div className="flex-1 min-h-0">
        {confirmedTemplate ? (
          <WSRReportPanel
            key={isoDate(weekStart)}
            startDate={isoDate(weekStart)}
            endDate={isoDate(weekEnd)}
            templateId={confirmedTemplate.id}
            mode="viewer"
            alwaysRegenerate
            onChangeTemplate={() => setStep("template")}
          />
        ) : null}
      </div>
    </div>
  );
}

// ── View WSR Page ─────────────────────────────────────────────────
// Implemented in src/components/ViewWSRPage.tsx

// ── View Daily Status Report Page ─────────────────────────────────
function completionPct(status: string): number {
  const s = normalizeStatus(status);
  if (s === "Done") return 100;
  if (s === "In Progress") return 50;
  return 0;
}

type TitleSpotlightCallbacks = {
  onPersistTitle?: (row: JiraStoryRecord, title: string) => Promise<void>;
  onRegenerateTitle?: (row: JiraStoryRecord) => Promise<string[]>;
};

function useTitleSpotlight(callbacks: TitleSpotlightCallbacks = {}) {
  const [expandedRow, setExpandedRow] = useState<JiraStoryRecord | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [highlightIdx, setHighlightIdx] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const generateAbortRef = useRef(0);

  const displayTitle = useCallback(
    (row: JiraStoryRecord) => row.title?.trim() || "—",
    [],
  );

  const isExpanded = useCallback(
    (jiraKey: string) => expandedRow?.jira_key === jiraKey,
    [expandedRow],
  );

  const toggleForRow = useCallback((row: JiraStoryRecord) => {
    generateAbortRef.current += 1;
    setSuggestions([]);
    setHighlightIdx(0);
    setIsGenerating(false);
    setExpandedRow((prev) => (prev?.jira_key === row.jira_key ? null : row));
  }, []);

  const close = useCallback(() => {
    setExpandedRow(null);
    setSuggestions([]);
    setIsGenerating(false);
    generateAbortRef.current += 1;
  }, []);

  const clearSuggestions = useCallback(() => {
    setSuggestions([]);
    setHighlightIdx(0);
  }, []);

  const commitTitle = useCallback(
    async (text: string) => {
      if (!expandedRow?.jira_key || !text.trim() || !callbacks.onPersistTitle) return;
      await callbacks.onPersistTitle(expandedRow, text.trim());
      close();
    },
    [expandedRow, callbacks, close],
  );

  const handleAiGenerate = useCallback(async () => {
    if (!expandedRow || !callbacks.onRegenerateTitle) return;
    const runId = ++generateAbortRef.current;
    setIsGenerating(true);
    setSuggestions([]);
    setHighlightIdx(0);
    try {
      const suggestions = await callbacks.onRegenerateTitle(expandedRow);
      if (generateAbortRef.current !== runId) return;
      setSuggestions(suggestions.filter((s) => s.trim()));
      setHighlightIdx(0);
    } catch {
      if (generateAbortRef.current === runId) setSuggestions([]);
    } finally {
      if (generateAbortRef.current === runId) setIsGenerating(false);
    }
  }, [expandedRow, callbacks]);

  return {
    expandedRow,
    expandedKey: expandedRow?.jira_key ?? null,
    suggestions,
    highlightIdx,
    isGenerating,
    displayTitle,
    isExpanded,
    toggleForRow,
    close,
    commitTitle,
    clearSuggestions,
    handleAiGenerate,
    setHighlightIdx,
  };
}

function useElementWidth(ref: React.RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const measure = () => setWidth(node.clientWidth);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(node);
    window.addEventListener("resize", measure);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [ref]);
  return width;
}

function InlineSummaryExpansionRow({
  colSpan,
  scrollRef,
  horizontalPad,
  children,
}: {
  colSpan: number;
  scrollRef: React.RefObject<HTMLDivElement | null>;
  horizontalPad: string;
  children: React.ReactNode;
}) {
  const portWidth = useElementWidth(scrollRef);
  return (
    <tr className="border-b border-gray-100">
      <td colSpan={colSpan} className="p-0">
        <div
          className={`sticky left-0 z-20 ${horizontalPad} py-3 pb-4 bg-gray-50 box-border`}
          style={
            portWidth > 0
              ? { width: portWidth, minWidth: portWidth, maxWidth: portWidth }
              : undefined
          }
        >
          {children}
        </div>
      </td>
    </tr>
  );
}

function InlineSummaryEditor({
  summary,
  contextLabel,
  fieldLabel = "Title",
  onClose,
  onCommit,
  onClearSuggestions,
  onAiGenerate,
  suggestions,
  isGenerating,
  highlightIdx,
  onHighlightChange,
}: {
  summary: string;
  contextLabel: string;
  fieldLabel?: string;
  onClose: () => void;
  onCommit: (text: string) => void;
  onClearSuggestions: () => void;
  onAiGenerate: () => void;
  suggestions: string[];
  isGenerating: boolean;
  highlightIdx: number;
  onHighlightChange: (i: number) => void;
}) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const fillSuggestion = useCallback(
    (text: string) => {
      setQuery(text);
      onClearSuggestions();
      requestAnimationFrame(() => inputRef.current?.focus());
    },
    [onClearSuggestions],
  );

  useEffect(() => {
    setQuery(summary);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [summary, contextLabel]);

  useEffect(() => {
    const onPointerDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (panelRef.current?.contains(target)) return;
      if ((target as Element).closest?.("[data-summary-toggle]")) return;
      onClose();
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [onClose]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === "ArrowDown" && suggestions.length > 0) {
        e.preventDefault();
        onHighlightChange(Math.min(highlightIdx + 1, suggestions.length - 1));
        return;
      }
      if (e.key === "ArrowUp" && suggestions.length > 0) {
        e.preventDefault();
        onHighlightChange(Math.max(highlightIdx - 1, 0));
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (document.activeElement === inputRef.current) {
          if (query.trim()) onCommit(query.trim());
        } else if (suggestions.length > 0 && suggestions[highlightIdx]) {
          fillSuggestion(suggestions[highlightIdx]);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [highlightIdx, suggestions, query, onHighlightChange, onCommit, onClose, fillSuggestion]);

  useEffect(() => {
    if (!listRef.current) return;
    listRef.current.querySelector(`[data-suggestion-idx="${highlightIdx}"]`)?.scrollIntoView({ block: "nearest" });
  }, [highlightIdx, suggestions.length]);

  return (
    <div
      ref={panelRef}
      className="w-full rounded-lg border border-brand-red/20 bg-white shadow-sm p-3 flex flex-col gap-3 text-left"
    >
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2.5 w-full">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={contextLabel ? `${fieldLabel} for ${contextLabel}…` : `Edit ${fieldLabel.toLowerCase()}…`}
          className="w-full min-w-0 px-3 py-2 border border-gray-300 rounded-md text-xs text-gray-800 placeholder:text-gray-400 bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-red/30 focus:border-brand-red/50"
          aria-label={`${fieldLabel} editor`}
        />
        <button
          type="button"
          onClick={onAiGenerate}
          disabled={isGenerating}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-semibold text-white bg-brand-orange hover:bg-brand-orange-hover disabled:opacity-60 transition-colors whitespace-nowrap shadow-sm"
        >
          <Sparkles className={`w-3.5 h-3.5 ${isGenerating ? "animate-pulse" : ""}`} />
          {isGenerating ? "…" : "Regenerate"}
        </button>
      </div>

      {isGenerating && suggestions.length === 0 && (
        <div className="rounded-md border border-dashed border-brand-red/30 bg-brand-red/10 px-3 py-2.5 text-xs text-gray-500">
          <Sparkles className="w-3.5 h-3.5 text-brand-red inline mr-1.5 animate-pulse" />
          Generating {fieldLabel.toLowerCase()}…
        </div>
      )}

      {!isGenerating && suggestions.length === 0 && (
        <p className="text-xs text-gray-400 px-0.5">
          Press <strong className="font-medium text-gray-500">Regenerate</strong> for a new AI {fieldLabel.toLowerCase()}, then <strong className="font-medium text-gray-500">Enter</strong> to save
        </p>
      )}

      {suggestions.length > 0 && (
        <div ref={listRef} className="flex flex-col gap-2 pt-1 border-t border-gray-100 max-h-52 overflow-y-auto spotlight-scroll pr-0.5">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 px-0.5 pt-0.5">
            Suggested {fieldLabel.toLowerCase()} — click to fill, then press Enter to save
          </p>
          {suggestions.map((text, i) => {
            const active = i === highlightIdx;
            return (
              <button
                key={i}
                type="button"
                data-suggestion-idx={i}
                onMouseEnter={() => onHighlightChange(i)}
                onClick={() => fillSuggestion(text)}
                className={`w-full text-left rounded-md px-3 py-2.5 text-xs border shadow-sm transition-colors opacity-0 animate-[spotlight-card-in_0.25s_ease-out_forwards] ${
                  active
                    ? "bg-brand-orange border-brand-red text-white shadow-md"
                    : "bg-white border-gray-200 text-gray-700 hover:bg-brand-red/10 hover:border-brand-red/40"
                }`}
                style={{ animationDelay: `${i * 80}ms` }}
              >
                <span className="leading-relaxed">{text}</span>
              </button>
            );
          })}
          <div className="h-1 flex-shrink-0" aria-hidden />
        </div>
      )}
    </div>
  );
}

function ClickableSummaryCell({
  text,
  onClick,
  expanded,
}: {
  text: string;
  onClick: () => void;
  expanded?: boolean;
}) {
  return (
    <button
      type="button"
      data-summary-toggle
      onClick={onClick}
      className={`block w-full max-w-xs text-left truncate text-xs font-normal bg-transparent border-0 p-0 m-0 cursor-pointer transition-colors ${
        expanded ? "text-brand-red font-medium" : "text-gray-700 hover:text-brand-red"
      }`}
      title={text}
      aria-expanded={expanded}
    >
      {text || "—"}
    </button>
  );
}

function sprintContainsDate(
  sprintStart: string,
  sprintEnd: string,
  dsrDate: string,
): boolean {
  const d = parseIsoDate(dsrDate.slice(0, 10));
  const start = parseIsoDate(sprintStart);
  const end = parseIsoDate(sprintEnd);
  if (!d || !start || !end) return false;
  return d >= start && d <= end;
}

function activeSprintLabelsForDsrDate(
  rows: JiraStoryRecord[],
  dsrDate: string,
): string[] {
  const names = new Set<string>();
  for (const row of rows) {
    const name = row.sprint_name?.trim();
    if (!name) continue;
    if (sprintContainsDate(row.sprint_start_date, row.sprint_end_date, dsrDate)) {
      names.add(name);
    }
  }
  return [...names].sort((a, b) => a.localeCompare(b));
}

function activeSprintMetaForDsrDate(
  rows: JiraStoryRecord[],
  dsrDate: string,
): { name: string; range: string }[] {
  return activeSprintLabelsForDsrDate(rows, dsrDate).map((name) => ({
    name,
    range: sprintDateRangeForName(rows as JiraIssue[], name),
  }));
}

function sortDsrDisplayRows(rows: JiraStoryRecord[]): JiraStoryRecord[] {
  return [...rows].sort((a, b) => {
    const aDone = normalizeStatus(a.status) === "Done" ? 1 : 0;
    const bDone = normalizeStatus(b.status) === "Done" ? 1 : 0;
    if (aDone !== bDone) return aDone - bDone;
    const aSnap = Date.parse((a.snapshot_date || "").slice(0, 10)) || 0;
    const bSnap = Date.parse((b.snapshot_date || "").slice(0, 10)) || 0;
    if (bSnap !== aSnap) return bSnap - aSnap;
    return a.jira_key.localeCompare(b.jira_key);
  });
}

function ViewDSRPage({ track }: { track: ImportedTrack }) {
  const [dsrDate, setDsrDate] = useState(() => todayIsoDate());
  const [rows, setRows] = useState<JiraStoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [historyJiraKey, setHistoryJiraKey] = useState<string | null>(null);
  const [commentJiraKey, setCommentJiraKey] = useState<string | null>(null);

  const trackCode = track.codes[0] ?? track.name;

  const loadTrackStories = useCallback(async () => {
    if (!track.projectId) {
      setRows([]);
      setFetchError("Track is missing project id — reload the page to sync with the API.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setFetchError("");
    try {
      const response = await fetchDsrStoriesByTrack(track.projectId, dsrDate);
      setRows(storiesToRecords(response.stories));
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : "Failed to load stories");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [track.projectId, dsrDate]);

  useEffect(() => {
    void loadTrackStories();
  }, [loadTrackStories, track.id]);

  const savedRows = rows.filter((r) => !r.isDraft);
  const draftRows = rows.filter((r) => r.isDraft);
  const displayRows = sortDsrDisplayRows([...savedRows, ...draftRows]);
  const allData = savedRows as JiraIssue[];

  const activeSprintMeta = activeSprintMetaForDsrDate(savedRows, dsrDate);

  const overallPct = statusCompletionPct(displayRows);
  const doneCount = displayRows.filter((r) => normalizeStatus(r.status) === "Done").length;
  const inProgressCount = displayRows.filter((r) => normalizeStatus(r.status) === "In Progress").length;
  const todoCount = displayRows.filter((r) => normalizeStatus(r.status) === "To Do").length;

  const patchDsrRow = useCallback((record: JiraStoryRecord) => {
    setRows((prev) => dedupeLatestRecords([
      ...prev.filter((r) => r.isDraft || r.jira_key !== record.jira_key),
      record,
    ]));
  }, []);

  const titleSpotlight = useTitleSpotlight({
    onPersistTitle: async (row, title) => {
      const payload = {
        ...recordToSavePayload(row, trackCode),
        title,
        snapshot_date: todayIsoDate(),
        updated_date: todayIsoDate(),
      };
      const saved = await updateStory(payload);
      patchDsrRow(apiStoryToRecord(saved));
    },
    onRegenerateTitle: async (row) => {
      const result = await regenerateStoryTitle(row.jira_key, row.snapshot_date);
      return result.suggestions;
    },
  });
  const tableScrollRef = useRef<HTMLDivElement>(null);

  const title = track.fullName ?? track.name;
  const tech = track.tech ?? "";
  const reporteeMap = useMemo(() => buildReporteeMap([track], allData), [track, allData]);

  const patchRow = (rowKey: string, patch: Partial<JiraStoryRecord>) => {
    setRows((prev) => prev.map((r) => (storyRowKey(r) === rowKey ? { ...r, ...patch } : r)));
  };

  const persistRow = async (row: JiraStoryRecord, patch: Partial<JiraStoryRecord> = {}) => {
    const originKey = storyRowKey(row);
    const versionDate = row.isDraft ? dsrDate : todayIsoDate();
    const merged = {
      ...row,
      ...patch,
      snapshot_date: versionDate,
      updated_date: todayIsoDate(),
    };
    if (!merged.summary?.trim() || merged.summary === "Story") {
      merged.summary = merged.title?.trim() || merged.summary || "Story";
    }
    setSavingKey(originKey);
    setSaveError("");
    try {
      const payload = recordToSavePayload(merged, trackCode);
      if (merged.isDraft) {
        const saved = await createStory(payload);
        const record = apiStoryToRecord(saved);
        setRows((prev) => dedupeLatestRecords([
          ...prev.filter((r) => storyRowKey(r) !== originKey),
          record,
        ]));
      } else {
        const saved = await updateStory(payload);
        const record = apiStoryToRecord(saved);
        setRows((prev) => dedupeLatestRecords([
          ...prev.filter((r) => r.isDraft || r.jira_key !== record.jira_key),
          record,
        ]));
      }
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save story");
    } finally {
      setSavingKey(null);
    }
  };

  const handleFieldSave = (row: JiraStoryRecord, field: keyof JiraStoryRecord, value: string | number | null) => {
    const rowKey = storyRowKey(row);
    patchRow(rowKey, { [field]: value } as Partial<JiraStoryRecord>);
    const updated = { ...row, [field]: value };
    if (row.isDraft) {
      if (updated.jira_key && updated.title?.trim()) {
        void persistRow(row, { [field]: value } as Partial<JiraStoryRecord>);
      }
    } else {
      void persistRow(updated);
    }
  };

  const addDraftRow = () => {
    setRows((prev) => [...prev, newDraftStory(track)]);
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      {historyJiraKey && (
        <StoryHistoryModal
          jiraKey={historyJiraKey}
          onClose={() => setHistoryJiraKey(null)}
        />
      )}
      {commentJiraKey && (
        <StoryCommentModal
          jiraKey={commentJiraKey}
          onClose={() => setCommentJiraKey(null)}
          onSubmit={async (comment) => {
            setSaveError("");
            const saved = await addStoryComment(commentJiraKey, comment);
            patchDsrRow(apiStoryToRecord(saved));
          }}
        />
      )}
      {fetchError ? (
        <div className="px-6 py-2 bg-red-50 border-b border-red-100 text-xs text-red-600">
          Could not load stories from API: {fetchError}
        </div>
      ) : null}
      {saveError ? (
        <div className="px-6 py-2 bg-amber-50 border-b border-amber-100 text-xs text-amber-700">
          Save failed: {saveError}
        </div>
      ) : null}
      {/* Header */}
      <div className="px-6 py-4 bg-white border-b border-gray-200 flex-shrink-0">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className="text-xs font-semibold text-brand-red bg-brand-red/10 border border-brand-red/20 px-2 py-0.5 rounded-full">
                {track.codes.join(" · ")}
              </span>
              {tech ? <span className="text-xs text-gray-400">{tech}</span> : null}
            </div>
            <h1 className="text-lg font-bold text-gray-900 leading-snug">{title}</h1>
          </div>

          <label className="flex items-center gap-2 shrink-0 px-3 py-2 rounded-lg border border-gray-200 bg-gray-50 text-xs text-gray-600">
            <Calendar className="w-3.5 h-3.5 text-brand-red shrink-0" />
            <span className="font-medium text-gray-500">DSR date</span>
            <input
              type="date"
              value={dsrDate.slice(0, 10)}
              onChange={(e) => setDsrDate(e.target.value)}
              className="px-2 py-0.5 border border-gray-200 rounded-md text-xs text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-brand-red/40"
            />
          </label>
        </div>

        <div className="mt-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-gray-400 mb-1.5">
            Active sprints
          </p>
          {activeSprintMeta.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {activeSprintMeta.map((sprint) => (
                <div
                  key={sprint.name}
                  className="inline-flex flex-wrap items-center gap-x-2 gap-y-0.5 max-w-full px-2.5 py-1.5 rounded-lg bg-gray-50 border border-gray-200 text-xs"
                >
                  <span className="font-semibold text-gray-800">{sprint.name}</span>
                  {sprint.range ? (
                    <span className="text-gray-500">{sprint.range}</span>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-400">
              {savedRows.length > 0
                ? "No sprint date ranges match the selected DSR date."
                : "No active sprints for this date."}
            </p>
          )}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {[
              { label: "Total", val: displayRows.length, cls: "bg-gray-100 text-gray-700" },
              { label: "To Do", val: todoCount, cls: "bg-gray-100 text-gray-500" },
              { label: "In Progress", val: inProgressCount, cls: "bg-blue-100 text-blue-700" },
              { label: "Done", val: doneCount, cls: "bg-green-100 text-green-700" },
            ].map((c) => (
              <div
                key={c.label}
                className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg ${c.cls}`}
              >
                <span className="text-sm font-bold leading-none tabular-nums">{c.val}</span>
                <span className="text-[11px] font-medium">{c.label}</span>
              </div>
            ))}
            <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-brand-red/10 text-brand-red">
              <span className="text-sm font-bold leading-none tabular-nums">{overallPct}%</span>
              <span className="text-[11px] font-medium">Complete</span>
            </div>
          </div>

          <div className="flex flex-1 min-w-[12rem] items-center gap-3">
            <span className="text-[11px] font-medium text-gray-500 shrink-0">Progress</span>
            <div className="flex-1 bg-gray-100 rounded-full h-2 min-w-[5rem]">
              <div
                className="h-2 rounded-full bg-brand-red transition-all"
                style={{ width: `${overallPct}%` }}
              />
            </div>
            <span className="text-[11px] font-semibold text-brand-red shrink-0 tabular-nums">
              {doneCount}/{displayRows.length}
            </span>
          </div>
        </div>
      </div>

      {/* Table */}
      <div ref={tableScrollRef} className="flex-1 overflow-auto">
        <table className="w-full text-xs border-collapse">
          <thead className="sticky top-0 bg-gray-50 z-10 border-b border-gray-200">
            <tr>
              {["Jira Key", "Title", "Date Assigned", "Status", "Comment", "Story Points", "% Complete", "Assignee", "Reportee"].map((h) => (
                <th key={h} className={`px-4 py-3 text-left text-xs font-semibold text-gray-500 whitespace-nowrap ${h === "Comment" ? "w-12 text-center" : ""}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={9} className="px-4 py-16 text-center text-gray-400">Loading stories from database…</td></tr>
            )}
            {!loading && displayRows.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-16 text-center text-gray-400">No stories in active sprints for this track on the selected DSR date.</td></tr>
            )}
            {!loading && displayRows.map((row, i) => {
              const record = row as JiraStoryRecord;
              const rowKey = storyRowKey(record);
              const pct = completionPct(row.status);
              const expanded = titleSpotlight.isExpanded(row.jira_key);
              const isSaving = savingKey === rowKey;
              return (
                <Fragment key={rowKey}>
                <tr className={`border-b border-gray-100 hover:bg-brand-red/10 ${record.isDraft ? "bg-amber-50/50" : ""} ${expanded ? "bg-brand-red/10" : i % 2 === 0 && !record.isDraft ? "bg-white" : !record.isDraft ? "bg-gray-50/30" : ""}`}>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {record.isDraft ? (
                      <DsrEditableInput
                        value={row.jira_key}
                        onSave={(v) => handleFieldSave(record, "jira_key", v)}
                        className="font-semibold text-brand-red min-w-28"
                      />
                    ) : (
                      <button
                        type="button"
                        disabled={!row.jira_key || isSaving}
                        onClick={() => setHistoryJiraKey(row.jira_key)}
                        className={`text-xs text-brand-red hover:text-brand-red hover:underline disabled:text-gray-400 disabled:no-underline disabled:cursor-default ${isSaving ? "opacity-50" : ""}`}
                        title="View version history"
                      >
                        {row.jira_key}
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-3 max-w-xs">
                    {record.isDraft ? (
                      <DsrEditableInput
                        value={row.title ?? ""}
                        onSave={(v) => handleFieldSave(record, "title", v)}
                        className="text-gray-800"
                      />
                    ) : (
                      <ClickableSummaryCell
                        text={titleSpotlight.displayTitle(record)}
                        expanded={expanded}
                        onClick={() => titleSpotlight.toggleForRow(record)}
                      />
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                    <DsrEditableInput
                      type="date"
                      value={(row.date_assigned ?? row.created_date ?? "").slice(0, 10)}
                      onSave={(v) => handleFieldSave(record, "date_assigned", v)}
                    />
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <DsrEditableStatus
                      value={row.status}
                      onSave={(v) => handleFieldSave(record, "status", v)}
                    />
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-center">
                    <button
                      type="button"
                      disabled={record.isDraft || !row.jira_key}
                      onClick={() => setCommentJiraKey(row.jira_key)}
                      title="Add comment"
                      className="inline-flex items-center justify-center w-7 h-7 rounded-md border border-gray-200 text-gray-500 hover:text-brand-red hover:border-brand-red/30 hover:bg-brand-red/10 disabled:opacity-40 disabled:pointer-events-none"
                    >
                      <MessageCircle className="w-3.5 h-3.5" />
                    </button>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <DsrEditableInput
                      type="number"
                      value={row.story_points != null ? String(row.story_points) : ""}
                      onSave={(v) => handleFieldSave(record, "story_points", v === "" ? null : Number(v))}
                      className="text-center w-14"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 min-w-24">
                      <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                        <div
                          className={`h-1.5 rounded-full transition-all ${pct === 100 ? "bg-green-500" : pct > 0 ? "bg-brand-red/100" : "bg-gray-200"}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className={`text-xs font-semibold w-8 text-right ${pct === 100 ? "text-green-600" : pct > 0 ? "text-blue-600" : "text-gray-400"}`}>{pct}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-700 whitespace-nowrap">
                    <DsrEditableInput
                      value={row.assignee ?? ""}
                      onSave={(v) => handleFieldSave(record, "assignee", v)}
                    />
                  </td>
                  <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                    <DsrEditableInput
                      value={record.reportee ?? record.reporter ?? getReporteeForAssignee(row.assignee, reporteeMap)}
                      onSave={(v) => handleFieldSave(record, "reportee", v)}
                    />
                  </td>
                </tr>
                {expanded && !record.isDraft && (
                  <InlineSummaryExpansionRow colSpan={9} scrollRef={tableScrollRef} horizontalPad="px-4">
                    <InlineSummaryEditor
                      summary={titleSpotlight.displayTitle(record)}
                      contextLabel={row.jira_key}
                      fieldLabel="Title"
                      onClose={titleSpotlight.close}
                      onCommit={(text) => { void titleSpotlight.commitTitle(text); }}
                      onClearSuggestions={titleSpotlight.clearSuggestions}
                      onAiGenerate={() => { void titleSpotlight.handleAiGenerate(); }}
                      suggestions={titleSpotlight.suggestions}
                      isGenerating={titleSpotlight.isGenerating}
                      highlightIdx={titleSpotlight.highlightIdx}
                      onHighlightChange={titleSpotlight.setHighlightIdx}
                    />
                  </InlineSummaryExpansionRow>
                )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Add story */}
      <div className="flex-shrink-0 border-t border-gray-200 bg-white px-6 py-3">
        <button
          type="button"
          onClick={addDraftRow}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-brand-red bg-brand-red/10 hover:bg-brand-red/10 border border-brand-red/30 rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add story
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("intake");
  const initialBundle = loadFromStorage();

  const [savedTickets, setSavedTickets] = useState<JiraIssue[]>(() => initialBundle.tickets);
  const [savedTracks, setSavedTracks] = useState<ImportedTrack[]>(() => initialBundle.tracks);
  const [trackCatalog, setTrackCatalog] = useState<TrackListItem[]>([]);
  const [wsrOpen, setWsrOpen] = useState(false);
  const [dsrOpen, setDsrOpen] = useState(false);
  const [selectedDsrTrack, setSelectedDsrTrack] = useState<ImportedTrack | null>(null);

  const refreshTrackCatalog = useCallback(async () => {
    try {
      const { tracks } = await fetchTeamTracks("HEB");
      setTrackCatalog(tracks);
      return tracks;
    } catch {
      return [];
    }
  }, []);

  useEffect(() => {
    void refreshTrackCatalog();
  }, [refreshTrackCatalog]);

  const dsrTrackList = useMemo(
    () =>
      catalogToImportedTracks(
        trackCatalog.filter(isViewDsrSidebarTrack),
      ) as ImportedTrack[],
    [trackCatalog],
  );

  useEffect(() => {
    if (dsrTrackList.length === 0) return;
    if (
      !selectedDsrTrack
      || !dsrTrackList.some(
        (t) => t.projectId === selectedDsrTrack.projectId
          || t.id === selectedDsrTrack.id,
      )
    ) {
      setSelectedDsrTrack(dsrTrackList[0]);
    }
  }, [dsrTrackList, selectedDsrTrack]);

  const handleImportComplete = (rows: JiraIssue[], tracks: ImportedTrack[]) => {
    setSavedTickets(rows);
    setSavedTracks(tracks);
    void refreshTrackCatalog();
  };

  return (
    <div className="flex h-screen bg-brand-cream font-[Inter,sans-serif]">
      <AppSidebar
        page={page}
        setPage={setPage}
        dsrOpen={dsrOpen}
        setDsrOpen={setDsrOpen}
        wsrOpen={wsrOpen}
        setWsrOpen={setWsrOpen}
        selectedDsrTrackId={selectedDsrTrack?.id}
        setSelectedDsrTrackId={(id) => {
          const track = dsrTrackList.find((t) => t.id === id);
          if (track) setSelectedDsrTrack(track);
        }}
        dsrTrackList={dsrTrackList}
        onRefreshTracks={() => {
          void refreshTrackCatalog();
        }}
      />

      {/* Main */}
      <main className="flex-1 flex flex-col min-w-0 bg-brand-cream">
        {page === "intake" ? (
          <DSREntryPage
            onImportComplete={handleImportComplete}
            onViewSavedTickets={() => setPage("complete-stories")}
            trackCatalog={trackCatalog}
            onTracksChanged={() => { void refreshTrackCatalog(); }}
          />
        ) : page === "complete-stories" ? (
          <SavedTicketsPage tracks={savedTracks} trackCatalog={trackCatalog} />
        ) : page === "view-dsr" ? (
          selectedDsrTrack ? (
            <ViewDSRPage track={selectedDsrTrack} />
          ) : (
            <div className="flex-1 flex items-center justify-center text-sm text-gray-500">
              Loading tracks…
            </div>
          )
        ) : page === "wsr-generate" ? (
          <GenerateWSRPage />
        ) : page === "wsr-view" ? (
          <ViewWSRPage />
        ) : null}
      </main>
    </div>
  );
}