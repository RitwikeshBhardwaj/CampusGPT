import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../auth"

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    try {
      await login(username, password)
      navigate("/", { replace: true })
    } catch {
      setError("That username and password didn't match.")
    }
  }

  return (
    <div className="login">
      <form className="login-card glass" onSubmit={handleSubmit}>
        <h1 className="wordmark">CampusGPT</h1>
        <p className="tagline">Ask the university's own documents.</p>
        <div className="field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        {error && <p className="form-error">{error}</p>}
        <button className="primary" type="submit">Log in</button>
      </form>
    </div>
  )
}
