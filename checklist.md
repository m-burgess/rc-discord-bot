# RC Discord Bot Development Checklist

## Phase 1: Core Foundation & Structure 
- [x] Initial project setup (uv package manager, virtual environment)
- [x] Clean architecture scaffold (domain, infrastructure, presentation)
- [x] Application configuration management
- [x] Basic Discord Bot setup & slash command synchronization

## Phase 2: Planning Center Integration (PCO)
- [x] PCO API client structure & async setup
- [x] Fetch upcoming plans & service items (run-sheets)
- [x] Fetch team rosters with volunteer status (Pending/Confirmed/Declined)
- [x] Map PCO names to Discord mentions dynamically via Discord Intent Cache
- [x] UI/UX: Interactive multi-team select dropdown menu for roster views
- [x] UI/UX: Dynamic timezone conversions (UTC to US Central)
- [x] Implement auto-reschedule slash commands for absent team members
- [x] Automated weekly schedule reminders with persistence and channel team mapping
- [x] Planning Center People household form integration (`/household_form`)

## Phase 3: Hardware Integration
- [ ] Connect and test Behringer WING integration over local network
- [ ] Connect and test Blackmagic ATEM switcher integration
- [ ] Implement Discord commands to trigger hardware scenes, cues, and macros
- [ ] Verify local network routing, security, and latency at the church location

## Phase 4: Production Readiness & Maintenance
- [ ] Setup long-term production deployment (e.g., `systemd` Linux service)
- [ ] Complete comprehensive documentation (README, architecture overview)
- [ ] Finalize persistent error handling and SQLite database logging
