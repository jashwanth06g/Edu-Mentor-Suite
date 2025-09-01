# 🎓 EduMentor Suite  

**Tech Stack:** Python | Flask | PostgreSQL | HTML | CSS | JavaScript  

EduMentor Suite is a **full-stack SaaS web application** designed as a **mentor-connect and learning platform**. It empowers **students, mentors, and admins** with tools for **personalized mentorship, real-time doubt resolution, learning modules, and performance tracking** — all in one platform.  

---

## 🚀 Key Features  

### 👨‍💼 Admin Portal  
- Add / remove **students** and **mentors**.  
- Track platform-wide performance and engagement.  
- Manage users and data with a **secure PostgreSQL backend**.  

### 🎓 Student Portal  
- Connect with mentors through **in-app chat**.  
- Access **structured learning modules** to build knowledge step by step.  
- Resolve doubts instantly via the **AI-powered chatbot**.  
- Attempt **in-app quizzes** to test understanding and measure progress.  

### 🧑‍🏫 Mentor Portal  
- Guide students using **direct in-app messaging**.  
- Review student **quiz performance** to identify strengths and weaknesses.  
- Monitor **learning module completion** and track progress.  
- Provide personalized feedback and mentorship.  

---

## 🔑 Highlights  
- **Three Role-Based Portals:** Admin, Student, Mentor.  
- **Learning Modules:** Structured educational content for guided learning.  
- **In-App Quizzes:** Students assess knowledge, mentors review results.  
- **Real-Time Messaging:** Seamless mentor–student interaction.  
- **AI-Powered Chatbot:** Quick doubt resolution using REST APIs.  
- **Scalable Backend:** Flask + PostgreSQL for reliability.  
- **Responsive UI:** Built with HTML, CSS, and JavaScript.  

---

## 🎥 Working Model Demo

👉 Click here to view demo

---

## 🏗️ System Architecture  

```mermaid
flowchart TD
    A[Admin Portal] -->|Add/Remove Users| D[(PostgreSQL Database)]
    A -->|Track Activity| D

    B[Student Portal] -->|In-App Chat| C[ Mentor Portal ]
    B -->|Attempt Quizzes| D
    B -->|Access Learning Modules| D
    B -->|Chatbot Queries| E[AI Chatbot API]

    C -->|Monitor Quizzes| D
    C -->|Track Learning Modules| D
    C -->|In-App Chat with Students| B

    D -->|Stores & Retrieves Data| A
    D --> B
    D --> C


