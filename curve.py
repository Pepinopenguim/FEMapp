import numpy as np
import math

class CurveHelper:
    @classmethod
    def calculate_parabola_points(cls, n_start: tuple[float, float], n_end: tuple[float, float], n_mid: tuple[float, float], segments:int=20):
        """
        Returns (points_unt, angles_deg) along the curve.
        """
        points_unt: list = []
        angles_deg = []

        xi_values = np.linspace(-1, 1, segments + 1)

        for xi in xi_values:
            #  Position Math (Shape Functions)
            N1 = -0.5 * xi * (1 - xi)
            N2 =  0.5 * xi * (1 + xi)
            N3 = (1 - xi**2)

            x = N1 * n_start[0] + N2 * n_end[0] + N3 * n_mid[0]
            y = N1 * n_start[1] + N2 * n_end[1] + N3 * n_mid[1]
            points_unt.append((float(x), float(y)))
            
            #  Tangent Math (Derivatives of Shape Functions dN/dxi)
            dN1 = -0.5 + xi
            dN2 =  0.5 + xi
            dN3 = -2.0 * xi
            
            dx_dxi = dN1 * n_start[0] + dN2 * n_end[0] + dN3 * n_mid[0]
            dy_dxi = dN1 * n_start[1] + dN2 * n_end[1] + dN3 * n_mid[1]
            
            #  Calculate Angle
            angle_rad = math.atan2(dy_dxi, dx_dxi)
            angles_deg.append(math.degrees(angle_rad))
        
        return points_unt, angles_deg

    @classmethod
    def calculate_circle_points(cls, n_start: tuple[float, float], n_end: tuple[float, float], n_mid: tuple[float, float], segments:int=50):
        """
        Returns (points_unt, angles_deg) representing a circular arc.
        """
        x1, y1 = n_start
        x2, y2 = n_end
        x3, y3 = n_mid

        # Find the Circumcenter (cx, cy)
        D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))

        # Fallback: Points are collinear (straight line)
        if abs(D) < 1e-10:
            x_vals = np.linspace(x1, x2, segments + 1)
            y_vals = np.linspace(y1, y2, segments + 1)
            points_unt = [(float(x), float(y)) for x, y in zip(x_vals, y_vals)]
            
            # Constant angle for straight line
            base_angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            angles_deg = [base_angle] * len(points_unt)
            return points_unt, angles_deg

        cx = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / D
        cy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / D
        r = math.hypot(x1 - cx, y1 - cy)

        theta1 = math.atan2(y1 - cy, x1 - cx)
        theta2 = math.atan2(y2 - cy, x2 - cx)

        sweep_2 = (theta2 - theta1) % (2 * math.pi)

        is_ccw = cls.is_curve_ccw(n_start, n_mid, n_end)

        if is_ccw:
            theta_end = theta1 + sweep_2
        else:
            theta_end = theta1 - (2 * math.pi - sweep_2)

        angles = np.linspace(theta1, theta_end, segments + 1)
        
        x_vals = cx + r * np.cos(angles)
        y_vals = cy + r * np.sin(angles)
        points_unt = [(float(x), float(y)) for x, y in zip(x_vals, y_vals)]
        
        # Calculate Tangents based on circular direction
        angles_deg = []
        for angle in angles:
            if is_ccw:
                tangent_rad = angle + (math.pi / 2) # 90 deg Forward
            else:
                tangent_rad = angle - (math.pi / 2) # 90 deg Backward
                
            normalized_angle = math.degrees(
                math.atan2(
                    math.sin(tangent_rad),
                    math.cos(tangent_rad)
                )
            )
            angles_deg.append(normalized_angle)
            
        return points_unt, angles_deg
    
    @classmethod
    def is_curve_ccw(cls, start: tuple[float, float], mid: tuple[float, float], end: tuple[float, float]) -> bool:
        """
        Determines if a 3-point curve turns Counter-Clockwise or Clockwise.
        Returns "CCW" or "CW".
        """
        x1, y1 = start
        x2, y2 = mid
        x3, y3 = end
        
        D = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
        
        return D > 0