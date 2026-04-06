# Client Onboarding Checklist

## Week 1: Initial Setup

### Pre-Launch Meeting
- [ ] Schedule 30-minute call with client
- [ ] Explain bot capabilities and limitations
- [ ] Clarify conversation flows for their business
- [ ] Collect required information:
  - [ ] Business name
  - [ ] Phone number
  - [ ] Email address
  - [ ] Preferred timezone
  - [ ] Operating hours
  - [ ] Available appointment slots

### Twilio Configuration
- [ ] Client creates Twilio account (https://www.twilio.com/console)
- [ ] Client provides Account SID
- [ ] Client provides Auth Token
- [ ] Client provides WhatsApp Phone Number
- [ ] **SECURELY** update .env with credentials (never share via email)
- [ ] Verify Twilio number is active and has WhatsApp enabled

### Database Setup
- [ ] Create tenant in database with client's slug
- [ ] Initialize tenant configuration with:
  - [ ] Business name
  - [ ] Business hours
  - [ ] Available time slots
  - [ ] Timezone
- [ ] Run initial database migration
- [ ] Verify database health

### Bot Configuration
- [ ] Customize greeting message with client's business name
- [ ] Configure time slots (morning/afternoon options)
- [ ] Set escalation reasons (pain types, urgency, etc.)
- [ ] Configure response templates in Spanish/Portuguese
- [ ] Test with 5 sample messages from client

### Webhook Registration
- [ ] Register webhook in Twilio console:
  - [ ] Inbound message webhook
  - [ ] Status callback webhook
- [ ] Verify webhook receives test messages
- [ ] Test end-to-end message flow

### Testing (Phase 1: Happy Path)
- [ ] Bot responds to greeting
- [ ] Bot asks for appointment
- [ ] Bot captures customer name/phone
- [ ] Bot offers time slots
- [ ] Bot confirms booking
- [ ] Bot sends confirmation message
- [ ] Response time < 2 seconds
- [ ] Message formatting looks good

### Testing (Phase 2: Edge Cases)
- [ ] Bot handles urgent complaints
- [ ] Bot escalates to human properly
- [ ] Bot detects "thanks" and goes silent
- [ ] Bot handles typos/misspellings
- [ ] Bot doesn't re-ask answered questions
- [ ] Bot works with accented characters (á, é, í, ó, ú)
- [ ] Bot works with emojis

### Launch Day
- [ ] Final end-to-end test
- [ ] Client sends test message
- [ ] Verify message is received and processed
- [ ] Bot responds appropriately
- [ ] Client approves response
- [ ] **GO LIVE** - Announce bot to customer base
- [ ] Monitor first 100 messages
- [ ] Be available for urgent support

---

## Week 2-4: Stabilization

### Daily Monitoring
- [ ] Check API health endpoint: `/api/health`
- [ ] Review error logs (none expected in happy path)
- [ ] Monitor response times (< 2s target)
- [ ] Count total messages processed
- [ ] Count escalations and verify appropriate

### Weekly Review
- [ ] Schedule 15-minute check-in with client
- [ ] Review conversation quality (sample 10 messages)
- [ ] Check for common patterns/issues
- [ ] Verify escalations were handled properly
- [ ] Measure booking success rate
  - Target: 70%+ of customers complete booking flow
  - (30% may abandon due to urgency, cancellation, etc.)

### Adjustments (If Needed)
- [ ] Refine conversation templates based on feedback
- [ ] Adjust time slot offerings
- [ ] Add/remove escalation reasons
- [ ] Improve response accuracy

### Documentation
- [ ] Create client-specific documentation
- [ ] Document custom slots/hours
- [ ] Document escalation process
- [ ] Create FAQ for staff

---

## Month 2+: Optimization

### Analytics & Reporting
- [ ] **Monthly metrics report:**
  - [ ] Total messages: ___
  - [ ] Booking completion rate: ____%
  - [ ] Average response time: ___ ms
  - [ ] Escalation rate: ____%
  - [ ] Customer satisfaction: ___/5

### Continuous Improvement
- [ ] Gather customer feedback
- [ ] Review failed conversations
- [ ] Test new conversation flows
- [ ] A/B test response variations

### Feature Requests
- [ ] Appointment reminders (SMS/WhatsApp)
- [ ] Calendar integration
- [ ] Multi-language support
- [ ] Advanced analytics
- [ ] Custom workflows

---

## Success Metrics

### Technical Metrics (Target)
| Metric | Target | Actual |
|--------|--------|--------|
| API Health | 99.9% uptime | __ |
| Response Time | < 2s | __ |
| Webhook Success | 99%+ | __ |
| Database Health | No errors | __ |
| Error Rate | < 0.1% | __ |

### Business Metrics (Client Goals)
| Metric | Target | Actual |
|--------|--------|--------|
| Booking Rate | 70%+ | __ |
| Customer Satisfaction | 4.5+/5 | __ |
| Escalation Rate | 5-15% | __ |
| Response Accuracy | 95%+ | __ |
| Daily Messages | [client goal] | __ |

---

## Client Communication Template

### Launch Announcement (Email)

```
Subject: Your WhatsApp Bot is Live! 🎉

Hi [Client Name],

Your WhatsApp bot is now live and ready to help your customers!

📱 Customer WhatsApp Number:
+1415-523-8886

✨ What the bot can do:
• Welcome customers 24/7
• Capture patient information
• Offer available appointment times
• Confirm bookings
• Escalate urgent cases to your staff

🧪 Test it out:
Send a message to +1415-523-8886 and say "Hola" or "Me duele la muela"

📊 Dashboard:
Access your dashboard at: https://yourdomain.com
Username: [client-email]
Password: [temporary-password]

❓ Questions?
Reply to this email or call [your phone]

Best regards,
Your Bot Team
```

### Weekly Check-in (Email)

```
Subject: Weekly Bot Report - [Client Name]

Hi [Client Name],

Here's your bot performance this week:

📊 Stats:
• Messages Processed: 247
• Booking Completion Rate: 73%
• Average Response Time: 1.2 seconds
• Escalations Handled: 18
• Customer Satisfaction: 4.7/5

📈 Highlights:
• Busiest day: Tuesday (52 messages)
• Most common request: Appointment booking
• No errors or downtime

🔧 Improvements Made:
• None (system performing well)

❓ Questions or feedback?
Let's schedule a quick call!

Best regards,
Your Bot Team
```

### Monthly Report (Email + Spreadsheet)

```
Subject: Monthly Bot Report - [Client Name]

Hi [Client Name],

Your bot's performance for [Month]:

📊 Executive Summary:
• Total Messages: 3,847
• New Customers Engaged: 312
• Appointments Booked: 289 (73% booking rate)
• Escalations Handled: 45
• System Uptime: 99.97%
• Customer Satisfaction: 4.6/5

📈 Trends:
• 12% increase in messages vs last month
• Peak hours: 10am-12pm, 4pm-6pm
• Most booked time slot: Afternoon (65%)

🎯 Recommendations:
1. Consider adding 2pm time slot (high demand)
2. Review escalation process - turnaround time excellent
3. Expand operating hours on Saturdays

🔄 Next Steps:
1. Schedule review call
2. Approve any new features
3. Plan for Q2 improvements

See attached detailed analytics spreadsheet.

Best regards,
Your Bot Team
```

---

## Troubleshooting Response Plan

### Issue: Bot Not Responding
1. [ ] Check API health: `curl https://yourdomain.com/api/health`
2. [ ] Check database connection in logs
3. [ ] Check LLM API (Groq) status
4. [ ] Restart API container
5. [ ] Contact support if persists

### Issue: Slow Responses (> 5s)
1. [ ] Check Groq API response time
2. [ ] Verify no database locks
3. [ ] Check server CPU/memory
4. [ ] Scale to larger instance if needed
5. [ ] Contact support if persists

### Issue: Messages Not Reaching Bot
1. [ ] Verify Twilio number is active
2. [ ] Check webhook URL in Twilio console
3. [ ] Verify tenant_slug in database
4. [ ] Check logs for parse errors
5. [ ] Contact Twilio support

### Issue: Wrong Responses
1. [ ] Verify LLM API key is correct
2. [ ] Check conversation state in database
3. [ ] Review conversation flow logic
4. [ ] Test with known good message
5. [ ] Gather feedback for tuning

---

## Handoff Documentation

### What Client Receives
- [ ] This checklist (mark items complete)
- [ ] Production deployment guide
- [ ] Dashboard access credentials
- [ ] Support contact information
- [ ] Twilio console link with instructions
- [ ] Architecture diagram
- [ ] Conversation flow diagram
- [ ] Sample conversation logs

### What You Keep Documented
- [ ] Client slug (tenant ID)
- [ ] Twilio Account SID
- [ ] Database details
- [ ] API key
- [ ] Support plan/SLA
- [ ] Escalation procedures
- [ ] Maintenance windows

---

## Post-Launch SLA

**Response Time**
- Critical bugs: 1 hour
- New features: 3-5 business days
- General support: 24 business hours

**Uptime Guarantee**
- 99.5% monthly uptime
- Exclude planned maintenance (communicated 48h ahead)
- Automated backups daily

**Support Channels**
- Email: support@yourdomain.com
- Phone: [your phone] (business hours)
- Dashboard: [status page]

---

## Success Celebration 🎉

Once client completes first 30 days successfully:
- [ ] Schedule congratulations call
- [ ] Share success metrics
- [ ] Discuss expansion opportunities
- [ ] Gather testimonial/case study
- [ ] Ask for referrals

---

**Document Version**: 1.0
**Created**: 2026-04-02
**Last Updated**: 2026-04-02
