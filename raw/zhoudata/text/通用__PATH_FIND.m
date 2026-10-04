initialPos = [0.1, 0.1];
initialV = [0, 0];
targets = [0.5,-0.5;0.5,-1.5;-0.5,-1.5;-1.5,-1.5;-2.5,-1.5;-3.5,-1.5;-4.5,-1.5;-5.5,-1.5;-5.5,-0.5;-5.5, 0.5;-4.5,0.5;-3.5,0.5;-2.5, 0.5; -1.5, 0.5;-1.5,1.5];
v0 = 0.28;
mode = 1; % 方格模式

[totalTime, finalPos] = simulateMotion(initialPos, initialV, targets, v0, mode);
%[pos, actualTime, time_points, trajectory] = simulateMotion(initialPos, initialV, targets, v0, totalTime);
fprintf('到达终点时间: %.4f 秒\n', totalTime);
fprintf('终点位置: (%.4f, %.4f)\n', finalPos(1), finalPos(2));
%fprintf('在 t = %.4f 秒时的位置: (%.4f, %.4f)\n', actualTime, pos(1), pos(2));
function [output1, output2, time_points, trajectory] = simulateMotion(initialPos, initialV, targets, v0, mode, varargin)
    % 参数说明:
    % initialPos: 初始位置 [x, y]
    % initialV:   初始速度 [vx, vy]
    % targets:    目标点矩阵, 每行一个目标 [x1,y1; x2,y2; ...]
    % v0:         目标速度大小 (标量)
    % mode:       模式选择 (1: 方格判断, 2: 0.25半径圆, 3: 0.05半径圆)
    % varargin:   可选参数，额外时间 (totalTime)
    %
    % 输出:
    % output1:    若未提供totalTime则为到达终点时间，否则为指定时刻位置
    % output2:    若未提供totalTime则为终点位置，否则为实际模拟时间
    % time_points:时间点序列
    % trajectory: 轨迹位置序列
    
    % 验证模式参数
    if ~ismember(mode, [1, 2, 3])
        error('无效的模式选择。请使用 1(方格), 2(0.25半径圆) 或 3(0.05半径圆)');
    end
    
    % 初始化参数
    dt = 1/30;             % 时间步长 (1/30秒)
    maxSteps = 10000;       % 最大迭代次数
    pos = initialPos;       % 当前位置
    v = initialV;           % 当前速度
    time = 0;              % 当前时间
    currentTargetIdx = 1;   % 当前目标索引
    reachedEnd = false;     % 是否到达终点标志
    totalTimeGiven = ~isempty(varargin);
    
    % 初始化轨迹记录
    trajectory = [pos];    % 位置轨迹
    time_points = [time];  % 时间轨迹
    
    if totalTimeGiven
        totalTime = varargin{1};
        % 确保totalTime是dt的整数倍
        totalTime = round(totalTime / dt) * dt;
    else
        totalTime = Inf;
    end

    % 主循环
    for step = 1:maxSteps
        % 检查是否到达最后一个目标点 (所有模式都使用精确到达判断)
        if currentTargetIdx == size(targets, 1)
            if norm(pos - targets(end, :)) < 0.05
                reachedEnd = true;
                break;
            end
        end
        
        % 根据模式检查是否进入当前目标点区域 (非最后一个目标点时切换)
        if currentTargetIdx < size(targets, 1)
            target = targets(currentTargetIdx, :);
            
            switch mode
                case 1 % 方格判断模式
                    % 计算目标点所在方格边界
                    xLow = floor(target(1));
                    xHigh = xLow + 1;
                    yLow = floor(target(2));
                    yHigh = yLow + 1;
                    
                    % 检查位置是否在方格内
                    inCondition = (pos(1) >= xLow && pos(1) < xHigh && ...
                                   pos(2) >= yLow && pos(2) < yHigh);
                    
                case 2 % 0.25半径圆模式
                    % 计算到目标的距离
                    dist = norm(pos - target);
                    inCondition = (dist <= 0.25);
                    
                case 3 % 0.05半径圆模式
                    % 计算到目标的距离
                    dist = norm(pos - target);
                    inCondition = (dist <= 0.05);
            end
            
            if inCondition
                currentTargetIdx = currentTargetIdx + 1;
            end
        end
        
        % 计算期望速度
        currentTarget = targets(currentTargetIdx, :);
        direction = currentTarget - pos;
        dist = norm(direction);
        
        if dist < 1e-5
            unitDir = [0, 0];
        else
            unitDir = direction / dist;
        end
        v_desired = v0 * unitDir;
        
        % 更新速度 (考虑惯性)
        v = v + (v_desired - v) * (4/15);
        
        % 检查是否需要部分时间步更新
        if totalTimeGiven && (time + dt > totalTime)
            delta_t = totalTime - time;
            pos = pos + v * delta_t;
            time = totalTime;
            % 记录最后位置
            trajectory = [trajectory; pos];
            time_points = [time_points; time];
            break;
        else
            % 正常更新位置和时间
            pos = pos + v * dt;
            time = time + dt;
            % 记录轨迹
            trajectory = [trajectory; pos];
            time_points = [time_points; time];
        end
        
        % 检查是否达到总时间
        if time >= totalTime
            break;
        end
    end
    
    % 绘制运动轨迹
    plotTrajectory(trajectory, targets, initialPos, mode);
    
    % 输出结果处理
    if totalTimeGiven
        output1 = pos;              % 返回指定时刻位置
        output2 = time;             % 返回实际模拟时间
    else
        if reachedEnd
            output1 = time;         % 返回到达终点时间
            output2 = pos;          % 返回终点位置
        else
            output1 = Inf;          % 未到达终点
            output2 = pos;          % 返回最终位置
            if step == maxSteps
                warning('未能在最大步数内到达终点（最大步数：10000）');
            end
        end
    end
end

function plotTrajectory(trajectory, targets, initialPos, mode)
    % 创建新图形窗口
    figure;
    
    % 绘制运动轨迹
    plot(trajectory(:,1), trajectory(:,2), 'b-', 'LineWidth', 1.5);
    hold on;
    grid on;
    
    % 标记起点
    plot(initialPos(1), initialPos(2), 'go', 'MarkerSize', 10, 'MarkerFaceColor', 'g');
    
    % 标记目标点
    for i = 1:size(targets, 1)
        target = targets(i, :);
        xLow = floor(target(1));
        xHigh = xLow + 1;
        yLow = floor(target(2));
        yHigh = yLow + 1;
                
                % 绘制方格
        rectangle('Position', [xLow, yLow, xHigh-xLow, yHigh-yLow], ...
                          'EdgeColor', 'k', 'LineStyle', '--');
        
        % 根据模式绘制不同的目标区域
        switch mode
            case 1 % 方格判断模式
                % 计算目标点所在方格边界
                
            case 2 % 0.25半径圆模式
                % 绘制圆形区域
                viscircles(target, 0.25, 'Color', 'k', 'LineStyle', '--');
                
            case 3 % 0.05半径圆模式
                % 绘制圆形区域
                viscircles(target, 0.05, 'Color', 'k', 'LineStyle', '--');
        end
        
        % 标记目标点
        plot(target(1), target(2), 'ro', 'MarkerSize', 8, 'MarkerFaceColor', 'r');
    end
    
    % 标记终点
    plot(trajectory(end,1), trajectory(end,2), 'mx', 'MarkerSize', 12, 'LineWidth', 2);
    
    % 添加标签和标题
    xlabel('X 坐标');
    ylabel('Y 坐标');
    
    % 根据模式添加标题
    switch mode
        case 1
            title('质点运动轨迹 (方格判断模式)');
        case 2
            title('质点运动轨迹 (0.25半径圆模式)');
        case 3
            title('质点运动轨迹 (0.05半径圆模式)');
    end
    
    legend('运动轨迹', '起点', '目标点', '终点', 'Location', 'best');
    
    % 设置坐标轴比例一致
    axis equal;
    
    % 添加网格
    grid on;
    box on;
    
    % 添加标注
    text(initialPos(1), initialPos(2), '起点', 'VerticalAlignment', 'bottom');
    for i = 1:size(targets, 1)
        text(targets(i,1), targets(i,2), sprintf('目标%d', i), 'VerticalAlignment', 'bottom');
    end
    text(trajectory(end,1), trajectory(end,2), '终点', 'VerticalAlignment', 'top');
    
    hold off;
end