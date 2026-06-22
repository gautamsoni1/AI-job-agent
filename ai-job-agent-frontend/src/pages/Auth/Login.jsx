const Login = () => {
  return (
    <div className="h-screen flex justify-center items-center">
      <div className="w-[400px] border rounded-lg p-6">
        <h1 className="text-2xl font-bold mb-5">
          Login
        </h1>

        <form>
          <input
            type="email"
            placeholder="Email"
            className="w-full border p-2 mb-3"
          />

          <input
            type="password"
            placeholder="Password"
            className="w-full border p-2 mb-3"
          />

          <button
            className="w-full bg-blue-600 text-white p-2 rounded"
          >
            Login
          </button>
        </form>
      </div>
    </div>
  );
};

export default Login;