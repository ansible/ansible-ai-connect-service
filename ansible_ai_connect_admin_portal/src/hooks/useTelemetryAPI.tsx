import { useEffect, useState } from "react";
import { Telemetry } from "../api/types";
import { getTelemetrySettings } from "../api/api";

export const useTelemetry = () => {
  const [telemetry, setTelemetry] = useState<Telemetry>({
    status: "NOT_ASKED",
  });

  useEffect(() => {
    let isMounted = true;
    setTelemetry({ status: "LOADING" });
    getTelemetrySettings()
      .then((response) => {
        if (isMounted) {
          const optOut = response.data["optOut"];
          setTelemetry({ status: "SUCCESS", data: { optOut: optOut } });
        }
      })
      .catch((error) => {
        setTelemetry({ status: "FAILURE", error: error });
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return telemetry;
};
