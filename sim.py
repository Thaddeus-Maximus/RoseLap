import numpy as np
import math

# Status Constant Definition
S_BRAKING = 1
S_ENG_LIM_ACC = 2
S_TIRE_LIM_ACC = 3
S_SUSTAINING = 4
S_DRAG_LIM = 5
S_SHIFTING = 6
S_TOPPED_OUT = 7

# Output Index Constant Definitions (Columns)
O_TIME = 0
O_DISTANCE = 1
O_VELOCITY = 2
O_NF = 3
O_NR = 4
O_SECTORS = 5
O_STATUS = 6
O_GEAR = 7
O_LONG_ACC = 8
O_LAT_ACC = 9
O_FR_REMAINING = 11
O_FF_REMAINING = 10
O_CURVATURE = 12
O_ENG_RPM = 13

# Shifting status codes
IN_PROGRESS = 0
JUST_FINISHED = 1
NOT_SHIFTING = 2


def step(vehicle, prior_result, segment, segment_next, brake, shifting, gear):
  """
  Takes a vehicle step. Returns (see last line) if successful, returns None if vehicle skids off into a wall.
  @param v0 the initial vehicle speed for this step
  @param segment the Segment of the track the vehicle is on
  @param brake a boolean value specifying whether or not to apply the brakes (with full available force)
  @param shifting a shifting status code
  """

  # init values
  Nf = prior_result[O_NF];
  Nr = prior_result[O_NR];
  v0 = prior_result[O_VELOCITY];
  x0 = prior_result[O_DISTANCE];
  t0 = prior_result[O_TIME];
  status = S_TOPPED_OUT
  F_longitudinal = 0

  Ff_lat = (1-vehicle.weight_bias)*segment.curvature*vehicle.mass*v0**2
  Fr_lat = vehicle.weight_bias*segment.curvature*vehicle.mass*v0**2
  
  Fr_lim = (vehicle.mu*Nr)
  Ff_lim = (vehicle.mu*Nf) 

  if Fr_lat > Fr_lim or Ff_lat > Ff_lim :
    return None

  Fr_remaining = np.sqrt(Fr_lim**2 - Fr_lat**2)

  Fr_engine_limit,eng_rpm = vehicle.eng_force(v0, int(gear))

  Ff_remaining = np.sqrt(Ff_lim**2 - Ff_lat**2)

  Fdown = vehicle.alpha_downforce()*v0**2;
  Fdrag = vehicle.alpha_drag()*v0**2;

  if brake:
    status = S_BRAKING
    F_brake = min(Ff_remaining/vehicle.front_brake_bias(), Fr_remaining/vehicle.rear_brake_bias())
    Fr_long = -F_brake*vehicle.rear_brake_bias()
    Ff_long = -F_brake*vehicle.front_brake_bias()
    # Fr_long = -Fr_remaining
    # Ff_long = -Ff_remaining
    gear = np.nan
  elif shifting:
    status = S_SHIFTING
    Fr_long = 0
    Ff_long = 0
    gear = np.nan
  else:
    status = S_ENG_LIM_ACC
    Fr_long = Fr_engine_limit
    if Fr_long > Fr_remaining:
      status = S_TIRE_LIM_ACC
      Fr_long = Fr_remaining
    Ff_long = 0


  a_long = (Fr_long+Ff_long-Fdrag)/vehicle.mass

  F_longitudinal = Ff_long+Fr_long - Fdrag
  a = F_longitudinal / vehicle.mass

  try:
    vf = math.sqrt(v0**2 + 2*a_long*segment.length)
  except:
    a_long=0
    vf=0

  if abs(F_longitudinal) < 1e-3 and shifting != IN_PROGRESS:
    status = S_DRAG_LIM
  if eng_rpm > vehicle.engine_rpms[-1]:
    status = S_TOPPED_OUT

  Nf = ( -vehicle.weight_bias*vehicle.g*vehicle.mass
      - Fdown*vehicle.weight_bias
      - vehicle.mass*a_long*vehicle.cg_height/vehicle.wheelbase_length
      + vehicle.mass*vehicle.g
      + Fdown
      - Fdrag*vehicle.cp_height/vehicle.wheelbase_length )

  Nr = ( vehicle.weight_bias*vehicle.g*vehicle.mass
      + Fdown*vehicle.cp_bias
      + vehicle.mass*a_long*vehicle.cg_height/vehicle.wheelbase_length
      + Fdrag*vehicle.cg_height/vehicle.wheelbase_length )

  Ff_lat = (1-vehicle.weight_bias)*segment_next.curvature*vehicle.mass*vf**2
  Fr_lat = vehicle.weight_bias*segment_next.curvature*vehicle.mass*vf**2
  
  Fr_lim = (vehicle.mu*Nr)
  Ff_lim = (vehicle.mu*Nf) 

  a_long_start = a_long
  
  nmax = 10
  n = 0
  while Fr_lat > Fr_lim-1e-2 or Ff_lat > Ff_lim-1e-2 :
    #return None
    a_long-=a_long_start*1/nmax
    vf = math.sqrt(v0**2 + 2*a_long*segment.length)

    Fdown = vehicle.alpha_downforce()*vf**2;
    Fdrag = vehicle.alpha_drag()*vf**2;

    Nf = ( -vehicle.weight_bias*vehicle.g*vehicle.mass
      - Fdown*vehicle.weight_bias
      - vehicle.mass*a_long*vehicle.cg_height/vehicle.wheelbase_length
      + vehicle.mass*vehicle.g
      + Fdown
      - Fdrag*vehicle.cp_height/vehicle.wheelbase_length )

    Nr = ( vehicle.weight_bias*vehicle.g*vehicle.mass
        + Fdown*vehicle.cp_bias
        + vehicle.mass*a_long*vehicle.cg_height/vehicle.wheelbase_length
        + Fdrag*vehicle.cg_height/vehicle.wheelbase_length )

    Ff_lat = (1-vehicle.weight_bias)*segment_next.curvature*vehicle.mass*vf**2
    Fr_lat = vehicle.weight_bias*segment_next.curvature*vehicle.mass*vf**2
    
    Fr_lim = (vehicle.mu*Nr)
    Ff_lim = (vehicle.mu*Nf)

    n+=1
    if n > nmax:
      return None

  try:
    tf = t0 + segment.length/((v0+vf)/2)
  except:
    tf = t0
  xf = x0 + segment.length

  output = np.array([
    tf,
    xf,
    vf,
    Nf,
    Nr, 
    segment.sector,
    status,
    gear,
    a_long / vehicle.g, 
    (v0 ** 2) * segment.curvature / vehicle.g, 
    Ff_remaining, 
    Fr_remaining, 
    segment.curvature,
    eng_rpm
  ])

  return output

def solve(vehicle, segments, output_0 = None):
  # set up initial stuctures
  output = np.zeros((len(segments), 14))
  precrash_output = np.zeros((len(segments), 14))
  shifting = NOT_SHIFTING
  
  if output_0 is None:
    output[0,3] = vehicle.mass*(1-vehicle.weight_bias)*vehicle.g
    output[0,4] = vehicle.mass*vehicle.weight_bias*vehicle.g
    gear = vehicle.best_gear(output[0,O_VELOCITY], np.inf)
  else:
    output[0,:] = output_0
    output[0,0] = 0
    output[0,1] = 0
    gear = vehicle.best_gear(output_0[O_VELOCITY], output_0[O_FR_REMAINING])

  brake = False
  shiftpt = -1
  shift_v_req = 0
  
  step_result = step(vehicle, output[0], segments[0], segments[1], brake, shiftpt>=0, gear)

  output[0] = step_result

  # step loop set up
  i = 1
  backup_amount = int(7.0/segments[0].length)
  bounds_found = False
  failpt = -1
  middle_brake_bound = -1
  lower_brake_bound = -1
  upper_brake_bound = -1

  while i<len(segments):
    if i<0:
      print('damnit bobby')
      return None
    if (gear is None) and shiftpt < 0:
      gear = vehicle.best_gear(output[i-1,O_VELOCITY], output[i,O_FR_REMAINING])

    step_result = step(vehicle,output[i-1,:], segments[i], (segments[i+1] if i+1<len(segments) else segments[i]), brake, shiftpt>=0, gear)
    if step_result is None:
      #print('crash at',i)
      if not brake:
        # Start braking

        #print('crash algo start at', i)
        precrash_output = np.copy(output)
        brake = True
        bounds_found = False
        failpt = i
        lower_brake_bound = i
        i = lower_brake_bound
        #plot_velocity_and_events(output)
        #plt.show()
      elif bounds_found:
        upper_brake_bound = middle_brake_bound

        middle_brake_bound = (upper_brake_bound+lower_brake_bound)/2
        #print('bisect down', lower_brake_bound, middle_brake_bound, upper_brake_bound)
        
        i = middle_brake_bound
        output = np.copy(precrash_output)
      else:
        # Try again from an earlier point
        
        lower_brake_bound-=backup_amount
        #print('push further', lower_brake_bound)

        i = lower_brake_bound
        output = np.copy(precrash_output)
      # reset shifting params
      gear = None
      shiftpt = -1
    elif i<=failpt:
      output[i] = step_result
      i+=1
      brake = True
      # reset shifting params
      gear = None
      shiftpt = -1
      shift_v_req = 0
    elif failpt>=0 and not bounds_found:
      #print('nailed it', lower_brake_bound)
      bounds_found = True

      upper_brake_bound = failpt-1 #lower_brake_bound+backup_amount

      middle_brake_bound = (upper_brake_bound+lower_brake_bound)/2
      
      i = middle_brake_bound
      output = np.copy(precrash_output)
    elif failpt>=0 and bounds_found and abs(lower_brake_bound - upper_brake_bound) > 1:
      lower_brake_bound = middle_brake_bound

      middle_brake_bound = (upper_brake_bound+lower_brake_bound)/2
      #print('bisect up', lower_brake_bound, middle_brake_bound, upper_brake_bound)
      
      i = middle_brake_bound
      output = np.copy(precrash_output)
    else:
      # normal operation

      # quit braking
      brake = False # problematic??
      failpt = -1
      lower_brake_bound = -1
      upper_brake_bound = -1
      bounds_found = False

      output[i] = step_result

      better_gear = vehicle.best_gear(output[i,O_VELOCITY], output[i,O_FR_REMAINING])

      if shiftpt < 0 and gear != better_gear and output[i,O_STATUS]==S_ENG_LIM_ACC and output[i,O_VELOCITY]>shift_v_req:
        gear += int((better_gear-gear)/abs(better_gear-gear))
        shiftpt = i
        shift_v_req = output[i,O_VELOCITY]*1.01
      elif shiftpt < 0 and output[i,O_STATUS]==S_TOPPED_OUT and gear<len(vehicle.gears)-1:
        gear += 1
        shiftpt = i
        shift_v_req = output[i,O_VELOCITY]*1.01

      if shiftpt >= 0 and output[i,O_TIME] > output[shiftpt,O_TIME]+vehicle.shift_time:
        shiftpt = -1
        i-=1
      
      i+=1

      

  #np.savetxt('dump.csv', output, delimiter=",")
  return output

def steady_solve(vehicle,segments):
  output = solve(vehicle,segments)
  return solve(vehicle,segments,output[-1, :])

def colorgen(num_colors, idx):
  color_norm  = colors.Normalize(vmin=0, vmax=num_colors-1)
  scalar_map = cmx.ScalarMappable(norm=color_norm, cmap='hsv') 
  def map_index_to_rgb_color(index):
    return scalar_map.to_rgba(index)
  return map_index_to_rgb_color(idx)

if __name__ == '__main__':
  import vehicle
  import track_segmentation
  import plottools

  vehicle.load("basic.yaml")

  track = './DXFs/ne_autocross_2015.dxf'
  segments = track_segmentation.dxf_to_segments(track, 0.1)

  #track_segmentation.plot_segments(segments)

  output = solve(vehicle.v, segments)

  plottools.plot_velocity_and_events(output)

  plottools.plt.show()