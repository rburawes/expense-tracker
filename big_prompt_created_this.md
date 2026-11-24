Build a complete expense tracking web app that helps users manage their personal finances. The app should feel modern, intuitive, and professional.

CORE FEATURES:
- Add expenses with date, amount, category, and description
- View expenses in a clean, organized list
- Filter expenses by date range and category
- Dashboard with spending summaries and basic analytics
- Categories: Food, Transportation, Entertainment, Shopping, Bills, Other
- Data persistence using sqlite for this demo

TECHNICAL REQUIREMENTS:

- Core:
	- Python 3.12+
	- Django 5.x
- Frontend:
	- Django templates
	- HTMX 2.x for dynamic partial updates (add/edit expenses without full page reloads)
	- Alpine.js 3 for small client-side interactions
    - Tailwind CSS v4 (via django-tailwind or similar) for styling with a modern, clean design
    - Django forms + django-crispy-forms
    - django-htmx for better integration
- Responsive design that works on desktop and mobile
- Form validation for expense inputs
- Date picker for expense dates
- Currency formatting for amounts

DESIGN REQUIREMENTS:
- Clean, modern interface with a professional color scheme
- Intuitive navigation and user experience
- Visual feedback for user actions
- Loading states and error handling
- Mobile-responsive design

SPECIFIC FUNCTIONALITY:
- Expense form with validation
- Expense list with search and filter capabilities
- Summary cards showing total spending, monthly spending, top categories
- Basic charts or visual representations of spending patterns
- Export functionality (at least CSV)
- Delete and edit existing expenses

Please create this as a complete, production-ready application. Set up the project structure, implement all features, and make sure everything works together seamlessly. Focus on creating something that looks professional and that I could actually use to track my expenses.

When you're done, provide instructions on how to run the application and test all features.